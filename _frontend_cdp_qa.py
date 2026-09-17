import base64
import json
import os
import random
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import urlparse


ROOT = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
APP_URL = "http://127.0.0.1:5000/"


class CDPWebSocket:
    def __init__(self, url):
        parsed = urlparse(url)
        self.host = parsed.hostname
        self.port = parsed.port
        self.path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")
        self.next_id = 1

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise RuntimeError("WebSocket closed")
            data += chunk
        return data

    def _send_frame(self, text):
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_frame(self):
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if opcode == 8:
            raise RuntimeError("WebSocket close frame")
        if opcode == 9:
            return self._recv_frame()
        return payload.decode("utf-8", errors="replace")

    def call(self, method, params=None, timeout=10):
        msg_id = self.next_id
        self.next_id += 1
        self._send_frame(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = json.loads(self._recv_frame())
            if message.get("id") == msg_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result", {})
        raise TimeoutError(method)


def wait_for_json(url, timeout=10):
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_err = exc
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_err}")


def runtime_eval(ws, expression, timeout=20):
    result = ws.call(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
            "timeout": timeout * 1000,
        },
        timeout=timeout + 2,
    )
    remote = result.get("result", {})
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"])
    return remote.get("value")


def capture(ws, name):
    data = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, timeout=10)
    path = os.path.join(ROOT, name)
    with open(path, "wb") as f:
        f.write(base64.b64decode(data["data"]))
    return path


def main():
    port = random.randint(9300, 9800)
    profile = tempfile.mkdtemp(prefix="fgai-cdp-qa-")
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--window-size=1365,900",
            APP_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        targets = wait_for_json(f"http://127.0.0.1:{port}/json/list", timeout=12)
        page = next(t for t in targets if t.get("type") == "page")
        ws = CDPWebSocket(page["webSocketDebuggerUrl"])
        ws.call("Runtime.enable")
        ws.call("Page.enable")
        runtime_eval(ws, "new Promise(r => setTimeout(r, 2500))")

        username = f"qa_ui_{int(time.time())}"
        register_result = runtime_eval(
            ws,
            f"""
            (async () => {{
                switchAuthTab('register');
                document.getElementById('auth-username').value = '{username}';
                document.getElementById('auth-password').value = 'secret123';
                await submitAuth();
                await new Promise(r => setTimeout(r, 1200));
                const recoveryModal = document.getElementById('recovery-code-modal');
                const recoveryVisible = recoveryModal && getComputedStyle(recoveryModal).display !== 'none';
                const recoveryCode = document.getElementById('recovery-code-value')?.textContent || '';
                if (recoveryVisible) closeRecoveryCodeModal();
                return {{
                    user: window.currentUser || currentUser,
                    recoveryVisible,
                    recoveryCodeLength: recoveryCode.length,
                    modal: getComputedStyle(document.getElementById('auth-modal')).display,
                    toast: (() => {{
                        const el = document.getElementById('toast');
                        const rect = el.getBoundingClientRect();
                        return {{
                            visible: el.classList.contains('show'),
                            text: el.textContent,
                            top: Math.round(rect.top)
                        }};
                    }})(),
                    loading: document.getElementById('app-loading')
                        ? getComputedStyle(document.getElementById('app-loading')).display
                        : 'removed'
                }};
            }})()
            """,
        )

        qa_script = r"""
        (async () => {
            const originalFetch = window.fetch.bind(window);
            const longRecipe = `# 第二次测试食谱\n\n## 食材\n- 西兰花 200g\n- 鸡蛋 2个\n- 番茄 2个\n\n## 做法\n1. 清洗并切配食材。\n2. 先炒鸡蛋，再加入番茄和西兰花。\n3. 小火收汁后装盘。\n\n## 营养说明\n这是一段较长内容，用来测试容器是否会被截断。`.repeat(8);
            const dailyRec = `# 明日饮食推荐\n\n1. 早餐增加水果和鸡蛋。\n2. 午餐补充深色蔬菜。\n3. 晚餐控制肉类摄入。`.repeat(6);
            const shoppingList = `## 广东省 深圳市南山区采购预算\n\n- 番茄 500g，参考单价 8-12 元/kg，小计 4-6 元\n- 鸡蛋 6个，参考单价 1.2-1.8 元/个，小计 7.2-10.8 元\n\n**预计总价：18-26 元**\n\n实际价格会因门店、季节和品牌而变化。`;

            function sseResponse(events) {
                const encoder = new TextEncoder();
                return new Response(new ReadableStream({
                    start(controller) {
                        for (const event of events) {
                            controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
                        }
                        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
                        controller.close();
                    }
                }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
            }

            window.__qaFetchCounts = {};
            window.fetch = async (url, options = {}) => {
                const path = String(url);
                window.__qaFetchCounts[path] = (window.__qaFetchCounts[path] || 0) + 1;
                if (path.includes('/api/generate_recipe_stream')) {
                    return sseResponse([
                        { content: longRecipe.slice(0, 900) },
                        { content: longRecipe.slice(900) },
                        { done: true, full_content: longRecipe, impact: { food_waste: 217.5, water: 108.75, carbon: 652.5 } }
                    ]);
                }
                if (path.includes('/api/generate_daily_recommendation_stream')) {
                    return sseResponse([{ content: dailyRec }, { done: true, full_content: dailyRec }]);
                }
                if (path.includes('/api/generate_shopping_list_stream')) {
                    return sseResponse([{ content: shoppingList }, { done: true, full_content: shoppingList }]);
                }
                if (path.includes('/api/save_intake')) {
                    return new Response(JSON.stringify({
                        success: true,
                        total_intake: { vegetables: 400, fruits: 220, meat: 90, eggs: 60 },
                        warnings: []
                    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                if (path.includes('/api/nutrition_assess')) {
                    return new Response(JSON.stringify({
                        success: true,
                        report: '# 营养评估\n\n今日摄入整体均衡，蔬菜和水果达到推荐区间。'
                    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                if (path.includes('/api/calculate_impact')) {
                    return new Response(JSON.stringify({
                        success: true,
                        impact: { food_waste: 217.5, water: 108.75, carbon: 652.5 }
                    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                return originalFetch(url, options);
            };

            function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
            function box(selector) {
                const el = document.querySelector(selector);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                const cs = getComputedStyle(el);
                return {
                    selector,
                    display: cs.display,
                    width: Math.round(r.width),
                    height: Math.round(r.height),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    overflowX: cs.overflowX,
                    overflowY: cs.overflowY,
                    text: (el.innerText || '').slice(0, 80)
                };
            }
            function findBadOverflow() {
                const selectors = [
                    '.app-shell', '.container', '.card', '.priority-card', '.guided-panel',
                    '#recipe-result', '#recipe-content', '#daily-rec-result-container',
                    '#daily-recommendation-content', '#home-assessment-result-container',
                    '#home-assessment-content', '#chat-messages', '#shopping-result-container',
                    '#shopping-result', '.tab-bar', '#auth-modal > div'
                ];
                const bad = [];
                for (const el of document.querySelectorAll(selectors.join(','))) {
                    const r = el.getBoundingClientRect();
                    const cs = getComputedStyle(el);
                    if (r.width <= 1 || r.height <= 1 || cs.display === 'none') continue;
                    const xBad = el.scrollWidth > el.clientWidth + 3 && !['auto', 'scroll', 'visible'].includes(cs.overflowX);
                    const yBad = el.scrollHeight > el.clientHeight + 3 && cs.overflowY === 'hidden';
                    if (xBad || yBad) {
                        bad.push({
                            id: el.id,
                            cls: el.className,
                            tag: el.tagName,
                            w: Math.round(r.width),
                            h: Math.round(r.height),
                            sw: el.scrollWidth,
                            cw: el.clientWidth,
                            sh: el.scrollHeight,
                            ch: el.clientHeight,
                            overflowX: cs.overflowX,
                            overflowY: cs.overflowY,
                            text: (el.innerText || '').slice(0, 50)
                        });
                    }
                }
                return bad;
            }

            const pages = {};
            for (const page of ['home', 'recipes', 'nutrition', 'chat', 'voice', 'fridge', 'shopping']) {
                switchPage(page);
                await wait(180);
                pages[page] = {
                    bodyOverflow: document.documentElement.scrollWidth - window.innerWidth,
                    active: document.querySelector('.page.active')?.id,
                    badOverflow: findBadOverflow(),
                    mainBox: box(`#page-${page}`)
                };
            }

            switchPage('recipes');
            document.getElementById('custom-ingredients').value = '西兰花,鸡蛋,番茄,鸡肉';
            appData.generation_count = 0;
            updateGenerationCounterDisplay(0);
            const first = await generateRecipe();
            const afterFirst = {
                result: box('#recipe-result'),
                content: box('#recipe-content'),
                count: appData.generation_count,
                htmlLength: document.getElementById('recipe-content').innerHTML.length,
                text: document.getElementById('recipe-content').innerText.slice(0, 120)
            };
            const concurrent = Promise.all([generateRecipe(), generateRecipe()]);
            await concurrent;
            const afterConcurrent = {
                result: box('#recipe-result'),
                content: box('#recipe-content'),
                count: appData.generation_count,
                htmlLength: document.getElementById('recipe-content').innerHTML.length,
                recipeCalls: window.__qaFetchCounts['/api/generate_recipe_stream'] || 0
            };
            await generateRecipe();
            const afterThirdRecipePage = {
                result: box('#recipe-result'),
                content: box('#recipe-content'),
                count: appData.generation_count,
                htmlLength: document.getElementById('recipe-content').innerHTML.length,
                dailyLength: document.getElementById('daily-recommendation-content').innerText.length,
                badOverflow: findBadOverflow()
            };
            switchPage('home');
            await wait(180);
            const afterThirdHomePage = {
                daily: box('#daily-rec-result-container'),
                assessment: box('#home-assessment-result-container'),
                badOverflow: findBadOverflow()
            };

            switchPage('chat');
            addChatMessage('这是一条很长很长很长的用户测试消息，用来检查聊天容器换行是否正常，不应该横向撑破页面。'.repeat(6), 'user');
            addChatMessage('这是 AI 回复内容。'.repeat(80), 'ai');
            await wait(100);
            const chat = { box: box('#chat-messages'), badOverflow: findBadOverflow() };

            switchPage('shopping');
            document.getElementById('shopping-dishes').value = '番茄炒蛋、清炒菜心';
            document.getElementById('shopping-people').value = '3';
            document.getElementById('shopping-province').value = '广东省';
            document.getElementById('shopping-city').value = '深圳市南山区';
            await generateShoppingList();
            await wait(3300);
            window.scrollTo(0, 0);
            await wait(180);
            const shopping = {
                result: box('#shopping-result-container'),
                locationPanel: box('#shopping-location-panel'),
                selectedRegion: document.getElementById('shopping-province').value + ' ' + document.getElementById('shopping-city').value,
                resultText: document.getElementById('shopping-result').innerText.slice(0, 160),
                badOverflow: findBadOverflow(),
                alignment: (() => {
                    const nav = document.querySelector('.tab-bar').getBoundingClientRect();
                    const page = document.querySelector('.page-container').getBoundingClientRect();
                    return { navTop: Math.round(nav.top), pageTop: Math.round(page.top), difference: Math.round(Math.abs(nav.top - page.top)) };
                })()
            };

            return {
                viewport: { width: innerWidth, height: innerHeight },
                pages,
                recipe: { afterFirst, afterConcurrent, afterThirdRecipePage, afterThirdHomePage },
                chat,
                shopping,
                bodyOverflow: document.documentElement.scrollWidth - window.innerWidth
            };
        })()
        """
        desktop_result = runtime_eval(ws, qa_script, timeout=40)
        desktop_shot = capture(ws, "_qa_frontend_shopping_desktop.png")
        runtime_eval(ws, "switchPage('voice'); new Promise(r => setTimeout(r, 500))")
        voice_shot = capture(ws, "_qa_frontend_voice_desktop.png")

        mobile_matrix = {}
        mobile_screenshots = []
        for width, height, label in [
            (320, 568, "320x568"),
            (360, 640, "360x640"),
            (390, 844, "390x844"),
            (430, 932, "430x932"),
            (844, 390, "844x390-landscape"),
        ]:
            ws.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 2, "mobile": True},
            )
            runtime_eval(ws, "switchPage('home'); new Promise(r => setTimeout(r, 220))")
            mobile_matrix[label] = runtime_eval(
                ws,
                """
                (() => {
                  const rect = (el) => {
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {
                      left: Math.round(r.left), right: Math.round(r.right),
                      top: Math.round(r.top), bottom: Math.round(r.bottom),
                      width: Math.round(r.width), height: Math.round(r.height)
                    };
                  };
                  const pages = {};
                  for (const page of ['home', 'recipes', 'nutrition', 'chat', 'voice', 'fridge', 'shopping']) {
                    switchPage(page);
                    const pageEl = document.querySelector(`#page-${page}`);
                    const pageRect = pageEl.getBoundingClientRect();
                    const firstCard = pageEl.querySelector('.card, .welcome-banner');
                    const cardRect = firstCard?.getBoundingClientRect();
                    pages[page] = {
                      bodyOverflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
                      pageOverflow: Math.max(0, pageEl.scrollWidth - pageEl.clientWidth),
                      pageGaps: {
                        left: Math.round(pageRect.left),
                        right: Math.round(innerWidth - pageRect.right),
                        difference: Math.round(Math.abs(pageRect.left - (innerWidth - pageRect.right)))
                      },
                      firstCardGaps: cardRect ? {
                        left: Math.round(cardRect.left),
                        right: Math.round(innerWidth - cardRect.right),
                        difference: Math.round(Math.abs(cardRect.left - (innerWidth - cardRect.right)))
                      } : null
                    };
                  }

                  const authModal = document.getElementById('auth-modal');
                  const previousAuthDisplay = authModal.style.display;
                  authModal.style.display = 'flex';
                  const authPanelElement = authModal.querySelector(':scope > div');
                  const authPanel = rect(authPanelElement);
                  const authLastAction = authPanelElement.querySelector('#auth-submit-btn');
                  authPanelElement.scrollTop = authPanelElement.scrollHeight;
                  const authLastActionAfterScroll = rect(authLastAction);
                  const authScroll = {
                    clientHeight: authPanelElement.clientHeight,
                    scrollHeight: authPanelElement.scrollHeight,
                    maxScroll: Math.max(0, authPanelElement.scrollHeight - authPanelElement.clientHeight),
                    lastActionAfterScroll: authLastActionAfterScroll,
                    actionReachable: Boolean(
                      authLastActionAfterScroll && authPanel &&
                      authLastActionAfterScroll.top >= authPanel.top - 1 &&
                      authLastActionAfterScroll.bottom <= authPanel.bottom + 1
                    )
                  };
                  authPanelElement.scrollTop = 0;
                  authModal.style.display = previousAuthDisplay;

                  const imageModal = document.getElementById('image-recognition-modal');
                  const previousImageDisplay = imageModal.style.display;
                  imageModal.style.display = 'flex';
                  const imagePanel = rect(imageModal.querySelector(':scope > div'));
                  const imageModalBody = imageModal.querySelector('.image-modal-body');
                  const imageActions = rect(imageModal.querySelector('.image-action-row'));
                  const imageActionButtons = [...imageModal.querySelectorAll('.image-action-row .btn')]
                    .map(rect);
                  imageModalBody.scrollTop = imageModalBody.scrollHeight;
                  const imageActionsAfterScroll = rect(imageModal.querySelector('.image-action-row'));
                  const imageScroll = {
                    clientHeight: imageModalBody.clientHeight,
                    scrollHeight: imageModalBody.scrollHeight,
                    maxScroll: Math.max(0, imageModalBody.scrollHeight - imageModalBody.clientHeight),
                    actionsAfterScroll: imageActionsAfterScroll,
                    actionsReachable: Boolean(
                      imageActionsAfterScroll && imagePanel &&
                      imageActionsAfterScroll.top >= imagePanel.top - 1 &&
                      imageActionsAfterScroll.bottom <= imagePanel.bottom + 1
                    )
                  };
                  imageModalBody.scrollTop = 0;
                  imageModal.style.display = previousImageDisplay;

                  const nav = document.querySelector('.tab-bar');
                  const navRect = nav.getBoundingClientRect();
                  const navItems = [...nav.querySelectorAll('.tab-item')];
                  const firstNavItem = navItems[0]?.getBoundingClientRect();
                  const lastNavItem = navItems.at(-1)?.getBoundingClientRect();
                  const logoRect = document.querySelector('.logo').getBoundingClientRect();
                  const actionRect = document.querySelector('.top-actions').getBoundingClientRect();
                  switchPage('home');

                  return {
                    viewport: { width: innerWidth, height: innerHeight },
                    bodyOverflow: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
                    pages,
                    topBar: {
                      logo: rect(document.querySelector('.logo')),
                      actions: rect(document.querySelector('.top-actions')),
                      overlap: Math.max(0, Math.round(logoRect.right - actionRect.left))
                    },
                    nav: {
                      box: rect(nav),
                      scrollOverflow: Math.max(0, nav.scrollWidth - nav.clientWidth),
                      allItemsVisible: Boolean(
                        firstNavItem && lastNavItem &&
                        firstNavItem.left >= navRect.left - 1 &&
                        lastNavItem.right <= navRect.right + 1
                      )
                    },
                    auth: {
                      panel: authPanel,
                      horizontalDifference: authPanel
                        ? Math.abs(authPanel.left - (innerWidth - authPanel.right))
                        : null,
                      scroll: authScroll,
                      fitsViewport: authPanel
                        ? authPanel.left >= 0 && authPanel.right <= innerWidth &&
                          authPanel.top >= 0 && authPanel.bottom <= innerHeight
                        : false
                    },
                    imageModal: {
                      panel: imagePanel,
                      actions: imageActions,
                      actionButtons: imageActionButtons,
                      scroll: imageScroll,
                      fitsViewport: imagePanel
                        ? imagePanel.left >= 0 && imagePanel.right <= innerWidth &&
                          imagePanel.top >= 0 && imagePanel.bottom <= innerHeight
                        : false
                    }
                  };
                })()
                """,
            )
            if label in ("320x568", "390x844", "844x390-landscape"):
                runtime_eval(ws, "switchPage('home'); new Promise(r => setTimeout(r, 180))")
                mobile_screenshots.append(capture(ws, f"_qa_frontend_mobile_{label}.png"))

        report = {
            "register": register_result,
            "desktop": desktop_result,
            "mobile": mobile_matrix,
            "screenshots": [desktop_shot, voice_shot, *mobile_screenshots],
        }
        report_path = os.path.join(ROOT, "_frontend_cdp_qa_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
