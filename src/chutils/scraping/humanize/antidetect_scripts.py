"""Генератор JavaScript-инъекций антидетекта для браузеров."""

from __future__ import annotations

import json
from typing import Any

DEFAULT_WEBGL_VENDOR = "Google Inc. (NVIDIA)"
DEFAULT_WEBGL_RENDERER = (
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
)
DEFAULT_HARDWARE_CONCURRENCY = 8
DEFAULT_DEVICE_MEMORY = 8


def _get_antidetect_js(
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
) -> str:
    """Генерирует JavaScript-инъекцию для скрытия признаков автоматизации браузера с заданными параметрами."""
    vendor_js = json.dumps(webgl_vendor)
    renderer_js = json.dumps(webgl_renderer)
    concurrency_js = int(hardware_concurrency)
    memory_js = int(device_memory)
    minimal_js = "true" if stealth_minimal else "false"
    seed_js = json.dumps(str(session_seed))
    hints_js = json.dumps(client_hints) if client_hints is not None else "null"

    return f"""(function() {{
    // Утилита для маскировки функций под нативные [native code] с чистым V8 stack trace
    const makeNative = (fn, name) => {{
        try {{
            Object.defineProperty(fn, 'name', {{ value: name, configurable: true }});
            const fnToString = function toString() {{ return `function ${{name}}() {{ [native code] }}`; }};
            fn.toString = fnToString;
            fn.toString.toString = function toString() {{ return "function toString() {{ [native code] }}"; }};
            if (Error.captureStackTrace) {{
                const origCapture = Error.captureStackTrace;
                Error.captureStackTrace = function(targetObj, constructorOpt) {{
                    origCapture(targetObj, constructorOpt || fn);
                    if (targetObj && targetObj.stack && typeof targetObj.stack === 'string') {{
                        targetObj.stack = targetObj.stack.replace(/at patched.*\\(eval at.*?\\)/g, `at ${{name}} (<anonymous>)`);
                    }}
                }};
            }}
        }} catch (e) {{}}
        return fn;
    }};

    // 0.1. Полноценная эмуляция объекта window.chrome
    try {{
        if (typeof window !== 'undefined') {{
            const chromeObj = window.chrome || {{}};
            if (!chromeObj.app) {{
                chromeObj.app = {{
                    isInstalled: false,
                    InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
                    RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }},
                    getDetails: makeNative(function() {{ return null; }}, 'getDetails'),
                    getIsInstalled: makeNative(function() {{ return false; }}, 'getIsInstalled'),
                    installState: makeNative(function() {{ return 'not_installed'; }}, 'installState'),
                    runningState: makeNative(function() {{ return 'cannot_run'; }}, 'runningState')
                }};
            }}
            if (!chromeObj.runtime) {{
                chromeObj.runtime = {{
                    OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }},
                    OnRestartRequiredReason: {{ APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }},
                    PlatformArch: {{ ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                    PlatformNaclArch: {{ ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                    PlatformOs: {{ ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }},
                    RequestUpdateCheckStatus: {{ NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }},
                    connect: makeNative(function() {{}}, 'connect'),
                    sendMessage: makeNative(function() {{}}, 'sendMessage')
                }};
            }}
            if (!chromeObj.loadTimes) {{
                chromeObj.loadTimes = makeNative(function loadTimes() {{
                    const now = Date.now() / 1000;
                    return {{
                        commitLoadTime: now,
                        connectionInfo: 'h2',
                        finishDocumentLoadTime: now,
                        finishLoadTime: now,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: now,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'h2',
                        requestTime: now - 0.2,
                        startLoadTime: now - 0.2,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: true,
                        wasNpnNegotiated: true
                    }};
                }}, 'loadTimes');
            }}
            if (!chromeObj.csi) {{
                chromeObj.csi = makeNative(function csi() {{
                    const now = Date.now();
                    return {{
                        onloadT: now,
                        pageT: 250.0,
                        startE: now - 250,
                        tran: 15
                    }};
                }}, 'csi');
            }}
            window.chrome = chromeObj;
        }}
    }} catch (e) {{}}

    // 0.2. Защита от утечек IP через WebRTC (RTCPeerConnection)
    try {{
        if (typeof window !== 'undefined' && window.RTCPeerConnection) {{
            const OrigPeerConnection = window.RTCPeerConnection;
            const filterCandidateSdp = (sdp) => {{
                if (typeof sdp !== 'string') return sdp;
                return sdp.replace(/a=candidate.* typ host .*\\r\\n/g, '');
            }};

            const PatchedPeerConnection = function RTCPeerConnection(config) {{
                const pc = new OrigPeerConnection(config);
                const origCreateOffer = pc.createOffer;
                pc.createOffer = function createOffer(options) {{
                    return origCreateOffer.apply(this, arguments).then((offer) => {{
                        if (offer && offer.sdp) {{
                            return new RTCSessionDescription({{
                                type: offer.type,
                                sdp: filterCandidateSdp(offer.sdp)
                            }});
                        }}
                        return offer;
                    }});
                }};
                makeNative(pc.createOffer, 'createOffer');

                const origCreateAnswer = pc.createAnswer;
                pc.createAnswer = function createAnswer(options) {{
                    return origCreateAnswer.apply(this, arguments).then((answer) => {{
                        if (answer && answer.sdp) {{
                            return new RTCSessionDescription({{
                                type: answer.type,
                                sdp: filterCandidateSdp(answer.sdp)
                            }});
                        }}
                        return answer;
                    }});
                }};
                makeNative(pc.createAnswer, 'createAnswer');
                return pc;
            }};
            PatchedPeerConnection.prototype = OrigPeerConnection.prototype;
            window.RTCPeerConnection = makeNative(PatchedPeerConnection, 'RTCPeerConnection');
        }}
    }} catch (e) {{}}

    // 0.3. Защита изолированных Web Workers и SharedWorkers
    try {{
        const workerPreamble = `
            try {{
                const navProto = Navigator.prototype || Object.getPrototypeOf(navigator);
                delete navProto.webdriver;
                delete navigator.webdriver;
                Object.defineProperty(navProto, 'webdriver', {{
                    get: () => undefined,
                    enumerable: true,
                    configurable: true
                }});
            }} catch (e) {{}}
        `;
        if (typeof window !== 'undefined' && window.Worker) {{
            const OriginalWorker = window.Worker;
            const PatchedWorker = function Worker(scriptURL, options) {{
                if (typeof scriptURL === 'string') {{
                    try {{
                        const blobContent = `${{workerPreamble}}\\nimportScripts("${{scriptURL}}");`;
                        const blob = new Blob([blobContent], {{ type: 'application/javascript' }});
                        const blobURL = URL.createObjectURL(blob);
                        return new OriginalWorker(blobURL, options);
                    }} catch (e) {{
                        return new OriginalWorker(scriptURL, options);
                    }}
                }}
                return new OriginalWorker(scriptURL, options);
            }};
            PatchedWorker.prototype = OriginalWorker.prototype;
            window.Worker = makeNative(PatchedWorker, 'Worker');
        }}
        if (typeof window !== 'undefined' && window.SharedWorker) {{
            const OriginalSharedWorker = window.SharedWorker;
            const PatchedSharedWorker = function SharedWorker(scriptURL, options) {{
                if (typeof scriptURL === 'string') {{
                    try {{
                        const blobContent = `${{workerPreamble}}\\nimportScripts("${{scriptURL}}");`;
                        const blob = new Blob([blobContent], {{ type: 'application/javascript' }});
                        const blobURL = URL.createObjectURL(blob);
                        return new OriginalSharedWorker(blobURL, options);
                    }} catch (e) {{
                        return new OriginalSharedWorker(scriptURL, options);
                    }}
                }}
                return new OriginalSharedWorker(scriptURL, options);
            }};
            PatchedSharedWorker.prototype = OriginalSharedWorker.prototype;
            window.SharedWorker = makeNative(PatchedSharedWorker, 'SharedWorker');
        }}
    }} catch (e) {{}}

    // Детерминированный LCG PRNG для Canvas шума
    const sessionSeed = {seed_js};
    let seedNum = 0;
    for (let i = 0; i < sessionSeed.length; i++) {{
        seedNum = ((seedNum << 5) - seedNum + sessionSeed.charCodeAt(i)) & 0xffffffff;
    }}
    const pseudoRandom = (offset) => {{
        const x = Math.sin(seedNum + offset) * 10000;
        return x - Math.floor(x);
    }};

    // 1. Скрытие и очистка navigator.webdriver
    const navProto = Navigator.prototype || Object.getPrototypeOf(navigator);
    try {{
        delete navProto.webdriver;
    }} catch (e) {{}}
    try {{
        delete navigator.webdriver;
    }} catch (e) {{}}
    try {{
        const webdriverGetter = makeNative(() => undefined, 'get webdriver');
        Object.defineProperty(navProto, 'webdriver', {{
            get: webdriverGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    const isMinimal = {minimal_js};

    if (!isMinimal) {{
        // 2. Рандомизация отпечатка Canvas с детерминированным шумом
        try {{
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            const patchedGetImageData = function getImageData(x, y, w, h) {{
                const imageData = originalGetImageData.apply(this, arguments);
                if (imageData && imageData.data && imageData.data.length >= 4) {{
                    const delta = pseudoRandom(x + y * 57) > 0.5 ? 1 : -1;
                    imageData.data[0] = (imageData.data[0] + delta) % 256;
                }}
                return imageData;
            }};
            CanvasRenderingContext2D.prototype.getImageData = makeNative(patchedGetImageData, 'getImageData');
        }} catch (e) {{}}

        // 3. Подмена WebGL параметров видеокарты (WebGL 1 и WebGL 2)
        const webglContexts = [];
        if (typeof WebGLRenderingContext !== 'undefined') webglContexts.push(WebGLRenderingContext);
        if (typeof WebGL2RenderingContext !== 'undefined') webglContexts.push(WebGL2RenderingContext);

        for (const ctx of webglContexts) {{
            try {{
                const originalGetParameter = ctx.prototype.getParameter;
                const patchedGetParameter = function getParameter(parameter) {{
                    // UNMASKED_VENDOR_WEBGL
                    if (parameter === 37445) {{
                        return {vendor_js};
                    }}
                    // UNMASKED_RENDERER_WEBGL
                    if (parameter === 37446) {{
                        return {renderer_js};
                    }}
                    return originalGetParameter.apply(this, arguments);
                }};
                ctx.prototype.getParameter = makeNative(patchedGetParameter, 'getParameter');
            }} catch (e) {{}}
        }}

        // 3.1. Детерминированный микрошум для AudioContext / OfflineAudioContext
        try {{
            const AudioBufferProto = typeof AudioBuffer !== 'undefined' ? AudioBuffer.prototype : null;
            if (AudioBufferProto && AudioBufferProto.getChannelData) {{
                const origGetChannelData = AudioBufferProto.getChannelData;
                AudioBufferProto.getChannelData = makeNative(function getChannelData(channel) {{
                    const data = origGetChannelData.apply(this, arguments);
                    if (data && data.length > 0) {{
                        const sampleIndex = Math.floor(pseudoRandom(channel * 101) * Math.min(data.length, 500));
                        const noise = (pseudoRandom(sampleIndex + 7) - 0.5) * 0.0000001;
                        data[sampleIndex] += noise;
                    }}
                    return data;
                }}, 'getChannelData');
            }}
        }} catch (e) {{}}
    }}

    // 4. Эмуляция navigator.plugins
    try {{
        const pluginsGetter = makeNative(() => {{
            return [
                {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
                {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdmgglogagaboenashesapgbbbi', description: 'Google Chrome PDF Viewer' }}
            ];
        }}, 'get plugins');
        Object.defineProperty(navigator, 'plugins', {{
            get: pluginsGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 5. Эмуляция hardwareConcurrency и deviceMemory
    try {{
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: makeNative(() => {concurrency_js}, 'get hardwareConcurrency'),
            enumerable: true,
            configurable: true,
        }});
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: makeNative(() => {memory_js}, 'get deviceMemory'),
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 5.1. Эмуляция размеров окна и экрана (outerWidth, outerHeight, availHeight)
    try {{
        if (typeof window !== 'undefined') {{
            if (window.outerWidth === 0 || window.outerHeight === 0 || window.outerHeight === window.innerHeight) {{
                const innerH = window.innerHeight || 800;
                const innerW = window.innerWidth || 1280;
                Object.defineProperty(window, 'outerWidth', {{
                    get: makeNative(() => innerW, 'get outerWidth'),
                    configurable: true,
                    enumerable: true
                }});
                Object.defineProperty(window, 'outerHeight', {{
                    get: makeNative(() => innerH + 85, 'get outerHeight'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if (typeof screen !== 'undefined') {{
                if (!screen.availHeight || screen.availHeight === screen.height) {{
                    Object.defineProperty(screen, 'availHeight', {{
                        get: makeNative(() => (screen.height ? screen.height - 40 : 1040), 'get availHeight'),
                        configurable: true,
                        enumerable: true
                    }});
                }}
            }}
        }}
    }} catch (e) {{}}

    // 5.2. Эмуляция navigator.connection и navigator.getBattery
    try {{
        if (!navigator.connection) {{
            const connectionObj = {{
                downlink: 10,
                effectiveType: '4g',
                rtt: 50,
                saveData: false,
                onchange: null
            }};
            Object.defineProperty(navigator, 'connection', {{
                get: makeNative(() => connectionObj, 'get connection'),
                enumerable: true,
                configurable: true
            }});
        }}
        if (!navigator.getBattery) {{
            const batteryManager = {{
                charging: true,
                chargingTime: 0,
                dischargingTime: Infinity,
                level: 1.0,
                onchargingchange: null,
                onchargingtimechange: null,
                ondischargingtimechange: null,
                onlevelchange: null
            }};
            navigator.getBattery = makeNative(function getBattery() {{
                return Promise.resolve(batteryManager);
            }}, 'getBattery');
        }}
    }} catch (e) {{}}

    // 6. Синхронизация Permissions API и Notification
    try {{
        if (navigator.permissions && navigator.permissions.query) {{
            const origQuery = navigator.permissions.query;
            const patchedQuery = function query(parameters) {{
                if (parameters && parameters.name === 'notifications' && typeof Notification !== 'undefined') {{
                    return Promise.resolve({{
                        state: Notification.permission === 'default' ? 'prompt' : Notification.permission,
                        onchange: null
                    }});
                }}
                return origQuery.apply(this, arguments);
            }};
            navigator.permissions.query = makeNative(patchedQuery, 'query');
        }}
    }} catch (e) {{}}

    // 7. Защита от извлечения прототипов через скрытый iframe (Cross-realm prototype inspection)
    try {{
        const originalCreateElement = Document.prototype.createElement;
        Document.prototype.createElement = makeNative(function createElement(tagName, options) {{
            const element = originalCreateElement.apply(this, arguments);
            if (element && typeof tagName === 'string' && tagName.toLowerCase() === 'iframe') {{
                element.addEventListener('load', function() {{
                    try {{
                        if (element.contentWindow) {{
                            const cw = element.contentWindow;
                            if (cw.Function && cw.Function.prototype) {{
                                cw.Function.prototype.toString = window.Function.prototype.toString;
                            }}
                            if (cw.navigator) {{
                                Object.defineProperty(cw.navigator, 'webdriver', {{
                                    get: makeNative(() => undefined, 'get webdriver'),
                                    enumerable: true,
                                    configurable: true
                                }});
                            }}
                        }}
                    }} catch (err) {{}}
                }});
            }}
            return element;
        }}, 'createElement');
    }} catch (e) {{}}

    // 8. Эмуляция Client Hints (navigator.userAgentData) при наличии hints
    const clientHintsData = {hints_js};
    if (clientHintsData) {{
        try {{
            const uaData = {{
                brands: clientHintsData.brands || [],
                mobile: Boolean(clientHintsData.mobile),
                platform: clientHintsData.platform || 'Windows',
                getHighEntropyValues: makeNative(function getHighEntropyValues(hints) {{
                    return Promise.resolve({{
                        brands: clientHintsData.brands || [],
                        mobile: Boolean(clientHintsData.mobile),
                        platform: clientHintsData.platform || 'Windows',
                        architecture: 'x86',
                        bitness: '64',
                        model: '',
                        platformVersion: '15.0.0',
                        uaFullVersion: (clientHintsData.brands && clientHintsData.brands[2] ? clientHintsData.brands[2].version : '120') + '.0.0.0'
                    }});
                }}, 'getHighEntropyValues')
            }};
            Object.defineProperty(navigator, 'userAgentData', {{
                get: makeNative(() => uaData, 'get userAgentData'),
                enumerable: true,
                configurable: true
            }});
        }} catch (e) {{}}
    }}
}})();"""
