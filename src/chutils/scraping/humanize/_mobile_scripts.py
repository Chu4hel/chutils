"""Генераторы JavaScript-скриптов для мобильных отпечатков, сенсорных и гироскопических событий."""

from __future__ import annotations


def get_touch_js(max_touch_points_val: int) -> str:
    """Возвращает JS-код для эмуляции Touch API.

    Args:
        max_touch_points_val: Максимальное количество точек касания для navigator.maxTouchPoints.

    Returns:
        Строка исполняемого JavaScript-кода эмуляции Touch API.
    """
    return f"""
    // 11. Эмуляция Touch API (Touch, TouchEvent, maxTouchPoints, ontouchstart)
    try {{
        if (typeof window !== 'undefined') {{
            if (!('ontouchstart' in window)) {{
                window.ontouchstart = null;
                window.ontouchend = null;
                window.ontouchmove = null;
                window.ontouchcancel = null;
            }}
            if (typeof document !== 'undefined' && !('ontouchstart' in document)) {{
                document.ontouchstart = null;
                document.ontouchend = null;
                document.ontouchmove = null;
                document.ontouchcancel = null;
            }}
            if (typeof navigator !== 'undefined') {{
                Object.defineProperty(navigator, 'maxTouchPoints', {{
                    get: makeNative(() => {max_touch_points_val}, 'get maxTouchPoints'),
                    configurable: true,
                    enumerable: true
                }});
            }}
            if (typeof window.TouchEvent === 'undefined') {{
                class Touch {{
                    constructor(touchInitDict = {{}}) {{
                        this.identifier = touchInitDict.identifier || 0;
                        this.target = touchInitDict.target || null;
                        this.screenX = touchInitDict.screenX || 0;
                        this.screenY = touchInitDict.screenY || 0;
                        this.clientX = touchInitDict.clientX || 0;
                        this.clientY = touchInitDict.clientY || 0;
                        this.pageX = touchInitDict.pageX || 0;
                        this.pageY = touchInitDict.pageY || 0;
                        this.radiusX = touchInitDict.radiusX || 10;
                        this.radiusY = touchInitDict.radiusY || 10;
                        this.rotationAngle = touchInitDict.rotationAngle || 0;
                        this.force = touchInitDict.force || 1.0;
                    }}
                }}
                class TouchEvent extends UIEvent {{
                    constructor(type, eventInitDict = {{}}) {{
                        super(type, eventInitDict);
                        this.touches = eventInitDict.touches || [];
                        this.targetTouches = eventInitDict.targetTouches || [];
                        this.changedTouches = eventInitDict.changedTouches || [];
                        this.altKey = !!eventInitDict.altKey;
                        this.metaKey = !!eventInitDict.metaKey;
                        this.ctrlKey = !!eventInitDict.ctrlKey;
                        this.shiftKey = !!eventInitDict.shiftKey;
                    }}
                }}
                window.Touch = makeNative(Touch, 'Touch');
                window.TouchEvent = makeNative(TouchEvent, 'TouchEvent');
            }}
        }}
    }} catch (e) {{}}
"""


def get_motion_js() -> str:
    """Возвращает JS-код для эмуляции DeviceOrientationEvent и DeviceMotionEvent.

    Returns:
        Строка исполняемого JavaScript-кода эмуляции гироскопа и акселерометра.
    """
    return """
    // 12. Эмуляция DeviceOrientationEvent и DeviceMotionEvent
    try {
        if (typeof window !== 'undefined') {
            if (typeof window.DeviceOrientationEvent === 'undefined') {
                class DeviceOrientationEvent extends Event {
                    constructor(type, eventInitDict = {}) {
                        super(type, eventInitDict);
                        this.alpha = eventInitDict.alpha !== undefined ? eventInitDict.alpha : 0;
                        this.beta = eventInitDict.beta !== undefined ? eventInitDict.beta : 90;
                        this.gamma = eventInitDict.gamma !== undefined ? eventInitDict.gamma : 0;
                        this.absolute = !!eventInitDict.absolute;
                    }
                }
                window.DeviceOrientationEvent = makeNative(DeviceOrientationEvent, 'DeviceOrientationEvent');
            }
            if (typeof window.DeviceMotionEvent === 'undefined') {
                class DeviceMotionEvent extends Event {
                    constructor(type, eventInitDict = {}) {
                        super(type, eventInitDict);
                        this.acceleration = eventInitDict.acceleration || { x: 0, y: 0, z: 0 };
                        this.accelerationIncludingGravity = eventInitDict.accelerationIncludingGravity || { x: 0, y: 9.8, z: 0 };
                        this.rotationRate = eventInitDict.rotationRate || { alpha: 0, beta: 0, gamma: 0 };
                        this.interval = eventInitDict.interval || 16;
                    }
                }
                window.DeviceMotionEvent = makeNative(DeviceMotionEvent, 'DeviceMotionEvent');
            }
        }
    } catch (e) {}
"""


def get_orientation_js(orientation_js: str, is_mobile_js: str) -> str:
    """Возвращает JS-код для эмуляции Screen Orientation.

    Args:
        orientation_js: JSON-строка параметров ориентации экрана.
        is_mobile_js: Строка 'true' или 'false' для флага мобильного режима.

    Returns:
        Строка исполняемого JavaScript-кода эмуляции Screen Orientation.
    """
    return f"""
    // 13. Эмуляция Screen Orientation
    try {{
        if (typeof window !== 'undefined' && typeof screen !== 'undefined') {{
            const orientData = {orientation_js} || ({is_mobile_js} ? {{ type: 'portrait-primary', angle: 0 }} : null);
            if (orientData) {{
                const screenOrientation = {{
                    type: orientData.type || 'portrait-primary',
                    angle: orientData.angle !== undefined ? orientData.angle : 0,
                    onchange: null,
                    lock: makeNative(() => Promise.resolve(), 'lock'),
                    unlock: makeNative(() => {{}}, 'unlock')
                }};
                Object.defineProperty(screen, 'orientation', {{
                    get: makeNative(() => screenOrientation, 'get orientation'),
                    configurable: true,
                    enumerable: true
                }});
            }}
        }}
    }} catch (e) {{}}
"""


def get_ios_js() -> str:
    """Возвращает JS-код для эмуляции объектов Safari на iOS (window.safari, window.ApplePaySession).

    Returns:
        Строка исполняемого JavaScript-кода эмуляции специфичных объектов iOS Safari.
    """
    return """
    // 14. Эмуляция iOS Safari (window.safari, window.ApplePaySession)
    try {
        if (typeof window !== 'undefined') {
            if (!window.safari) {
                window.safari = {
                    pushNotification: {
                        toString: makeNative(() => '[object SafariRemoteNotification]', 'toString'),
                        permission: makeNative(() => ({ permission: 'default' }), 'permission'),
                        requestPermission: makeNative(() => {}, 'requestPermission')
                    }
                };
            }
            if (!window.ApplePaySession) {
                class ApplePaySession {
                    static canMakePayments() { return true; }
                    static canMakePaymentsWithActiveCard() { return Promise.resolve(false); }
                    static supportsVersion() { return true; }
                }
                window.ApplePaySession = makeNative(ApplePaySession, 'ApplePaySession');
            }
        }
    } catch (e) {}
"""
