import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const isMobile = () => /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || window.innerWidth < 768

const GATEWAY_TOKEN = import.meta.env.VITE_GATEWAY_TOKEN || 'soalin-gateway-token'
const SESSION_KEY = 'soalin:main'

function resolveUrls() {
  const gwEnv = import.meta.env.VITE_GATEWAY_URL || ''
  const ssEnv = import.meta.env.VITE_SCREENSHOT_URL || ''
  if (gwEnv && gwEnv !== '__SAME_ORIGIN__') {
    return { wsUrl: gwEnv, ssUrl: ssEnv || 'http://localhost:3001' }
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return {
    wsUrl: proto + '//' + location.host + '/ws',
    ssUrl: location.origin + '/api'
  }
}
const { wsUrl: GATEWAY_URL, ssUrl: SCREENSHOT_URL } = resolveUrls()

interface ChatEntry {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  streaming?: boolean
}

type View = 'main' | 'settings'

let reqIdCounter = 0
function nextReqId() {
  return `soalin-${Date.now()}-${++reqIdCounter}`
}

function App() {
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([
    { role: 'system', content: 'Soalin v5.0 (OpenClaw) - AI browser control. Try: "Open YouTube", "Search Google for weather"', timestamp: Date.now() }
  ])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [currentView, setCurrentView] = useState<View>('main')
  const [screenHeight, setScreenHeight] = useState(45)
  const [screenshot, setScreenshot] = useState<string>('')
  const [streamingText, setStreamingText] = useState('')
  const [gatewayStatus, setGatewayStatus] = useState<string>('Connecting...')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null)
  const [inputFocused, setInputFocused] = useState(false)
  const [vpStyle, setVpStyle] = useState<{ height: number; top: number }>({ height: window.innerHeight, top: 0 })
  const pendingRef = useRef<Map<string, (res: unknown) => void>>(new Map())
  const connectedRef = useRef(false)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [chatMessages, scrollToBottom])

  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const update = () => {
      setVpStyle({ height: vv.height, top: vv.offsetTop })
    }
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    return () => {
      vv.removeEventListener('resize', update)
      vv.removeEventListener('scroll', update)
    }
  }, [])

  const sendWsRequest = useCallback((method: string, params: Record<string, unknown>): Promise<unknown> => {
    return new Promise((resolve, reject) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        reject(new Error('Not connected'))
        return
      }
      const id = nextReqId()
      const timeout = setTimeout(() => {
        pendingRef.current.delete(id)
        reject(new Error('Request timeout'))
      }, 120000)
      pendingRef.current.set(id, (res) => {
        clearTimeout(timeout)
        resolve(res)
      })
      ws.send(JSON.stringify({ type: 'req', id, method, params }))
    })
  }, [])

  const connectGateway = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    if (wsRef.current) {
      wsRef.current.close()
    }

    setGatewayStatus('Connecting...')
    const ws = new WebSocket(GATEWAY_URL)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'event' && data.event === 'connect.challenge') {
          const connectReq = {
            type: 'req',
            id: nextReqId(),
            method: 'connect',
            params: {
              minProtocol: 3,
              maxProtocol: 3,
              client: {
                id: 'openclaw-control-ui',
                displayName: 'Soalin',
                version: '5.0.0',
                platform: 'web',
                mode: 'ui'
              },
              role: 'operator',
              scopes: ['operator.admin'],
              caps: [],
              commands: [],
              permissions: {},
              auth: { token: GATEWAY_TOKEN },
              locale: navigator.language || 'ja-JP',
              userAgent: 'soalin-web/5.0.0'
            }
          }
          pendingRef.current.set(connectReq.id, (res: unknown) => {
            const r = res as { ok?: boolean; payload?: { type?: string } }
            if (r.ok && r.payload?.type === 'hello-ok') {
              connectedRef.current = true
              setIsConnected(true)
              setGatewayStatus('Connected to OpenClaw')
            }
          })
          ws.send(JSON.stringify(connectReq))
          return
        }

        if (data.type === 'res') {
          const handler = pendingRef.current.get(data.id)
          if (handler) {
            pendingRef.current.delete(data.id)
            handler(data)
          }
          return
        }

        if (data.type === 'event' && data.event === 'chat') {
          const payload = data.payload
          if (payload.state === 'delta') {
            const msg = payload.message
            if (msg && msg.content) {
              const contentArr = Array.isArray(msg.content) ? msg.content : [msg.content]
              let text = ''
              for (const block of contentArr) {
                if (typeof block === 'string') text += block
                else if (block && typeof block.text === 'string') text += block.text
              }
              if (text) {
                setStreamingText(prev => prev + text)
              }
            }
          } else if (payload.state === 'final') {
            const msg = payload.message
            let text = ''
            if (msg && msg.content) {
              const contentArr = Array.isArray(msg.content) ? msg.content : [msg.content]
              for (const block of contentArr) {
                if (typeof block === 'string') text += block
                else if (block && typeof block.text === 'string') text += block.text
              }
            }
            setStreamingText('')
            setIsLoading(false)
            if (text) {
              setChatMessages(prev => {
                const filtered = prev.filter(m => !m.streaming)
                return [...filtered, { role: 'assistant', content: text, timestamp: Date.now() }]
              })
            }
          } else if (payload.state === 'error') {
            setStreamingText('')
            setIsLoading(false)
            setChatMessages(prev => {
              const filtered = prev.filter(m => !m.streaming)
              return [...filtered, { role: 'assistant', content: 'Error: ' + (payload.errorMessage || 'Unknown error'), timestamp: Date.now() }]
            })
          }
          return
        }

      } catch { /* ignore parse errors */ }
    }

    ws.onopen = () => {
      setGatewayStatus('Authenticating...')
    }

    ws.onclose = () => {
      connectedRef.current = false
      setIsConnected(false)
      setGatewayStatus('Disconnected')
      if (!reconnectTimerRef.current) {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null
          connectGateway()
        }, 3000)
      }
    }

    ws.onerror = () => {
      setGatewayStatus('Connection error')
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connectGateway()
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
    }
  }, [connectGateway])

  useEffect(() => {
    if (streamingText) {
      setChatMessages(prev => {
        const filtered = prev.filter(m => !m.streaming)
        return [...filtered, { role: 'assistant', content: streamingText, timestamp: Date.now(), streaming: true }]
      })
    }
  }, [streamingText])

  const fetchScreenshot = useCallback(async () => {
    if (!connectedRef.current) return
    try {
      const res = await fetch(SCREENSHOT_URL + '/screenshot')
      if (res.ok) {
        const data = await res.json()
        if (data.image) {
          setScreenshot(data.image)
        }
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    if (!isConnected) return
    fetchScreenshot()
    const interval = setInterval(fetchScreenshot, 2000)
    return () => clearInterval(interval)
  }, [isConnected, fetchScreenshot])

  const sendChatMessage = async (message: string) => {
    setChatMessages(prev => [...prev, { role: 'user', content: message, timestamp: Date.now() }])
    setIsLoading(true)
    setStreamingText('')
    try {
      const idempotencyKey = 'soalin-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8)
      await sendWsRequest('chat.send', {
        sessionKey: SESSION_KEY,
        message,
        idempotencyKey,
        timeoutMs: 120000
      })
    } catch (err) {
      setIsLoading(false)
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error: ' + (err instanceof Error ? err.message : 'Failed to send'),
        timestamp: Date.now()
      }])
    }
  }

  const sendMessage = async () => {
    const message = inputText.trim()
    if (!message || isLoading) return
    setInputText('')
    await sendChatMessage(message)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const quickActions = [
    { label: 'YouTube', cmd: 'Open YouTube' },
    { label: 'Google', cmd: 'Open Google' },
    { label: 'Screenshot', cmd: 'Take a screenshot' },
    { label: 'Scroll Down', cmd: 'Scroll down' },
    { label: 'Scroll Up', cmd: 'Scroll up' },
    { label: 'Back', cmd: 'Go back' },
    { label: 'New Tab', cmd: 'Open new tab' },
  ]

  const browserRequest = useCallback(async (method: string, path: string, body?: Record<string, unknown>) => {
    return sendWsRequest('browser.request', { method, path, body })
  }, [sendWsRequest])

  const startBrowser = useCallback(async () => {
    try {
      await browserRequest('POST', '/start')
    } catch { /* ignore */ }
  }, [browserRequest])

  useEffect(() => {
    if (isConnected) { startBrowser() }
  }, [isConnected, startBrowser])

  const handleScreenClick = async (e: React.MouseEvent<HTMLImageElement>) => {
    const img = e.currentTarget
    const rect = img.getBoundingClientRect()
    const scaleX = 1280 / rect.width
    const scaleY = 800 / rect.height
    const x = Math.round((e.clientX - rect.left) * scaleX)
    const y = Math.round((e.clientY - rect.top) * scaleY)
    sendChatMessage('Click at coordinates (' + x + ', ' + y + ')')
  }

  const handleDividerPointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    dragRef.current = { startY: e.clientY, startHeight: screenHeight }
    const onMove = (ev: PointerEvent) => {
      if (!dragRef.current) return
      const delta = ev.clientY - dragRef.current.startY
      const vh = (delta / window.innerHeight) * 100
      const next = Math.max(20, Math.min(80, dragRef.current.startHeight + vh))
      setScreenHeight(next)
    }
    const onUp = () => {
      dragRef.current = null
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  if (currentView === 'settings') {
    return (
      <div className="flex flex-col h-screen bg-gray-950 text-white">
        <div className="flex items-center px-4 py-3 bg-gray-800 border-b border-gray-700">
          <button onClick={() => setCurrentView('main')} className="text-blue-400 text-sm mr-3">Back</button>
          <h2 className="text-sm font-semibold">Settings</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">OpenClaw Gateway</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Status</span>
                <span className={'text-xs px-2 py-0.5 rounded-full ' + (isConnected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300')}>{gatewayStatus}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Gateway URL</span>
                <span className="text-xs text-gray-400 font-mono">{GATEWAY_URL}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Session Key</span>
                <span className="text-xs text-gray-400 font-mono">{SESSION_KEY}</span>
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">AI Engine</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Primary</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-900 text-purple-300">Claude Sonnet 4</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Fallback</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900 text-blue-300">GPT-4o</span>
              </div>
              <p className="text-xs text-gray-500">Powered by OpenClaw Gateway. Models configured server-side.</p>
            </div>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">Browser Control</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Engine</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-orange-900 text-orange-300">Playwright</span>
              </div>
              <p className="text-xs text-gray-500">DOM ref-based operations: click, type, drag, hover, and more.</p>
            </div>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">About</h3>
            <div className="bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-300">Soalin v5.0 (OpenClaw Edition)</p>
              <p className="text-xs text-gray-500 mt-1">AI PC control via OpenClaw + Playwright</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const mobileTyping = inputFocused && isMobile()

  return (
    <div className="flex flex-col bg-gray-950 text-white select-none" style={{ position: 'fixed', top: vpStyle.top, left: 0, right: 0, height: vpStyle.height, overflow: 'hidden' }}>
      <div className="relative flex-shrink-0 bg-black transition-all duration-200" style={{ height: mobileTyping ? (vpStyle.height * screenHeight / 100) + 'px' : screenHeight + 'vh' }}>
        <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
          <div className={'w-2 h-2 rounded-full ' + (isConnected ? 'bg-green-500' : 'bg-red-500')} />
          <span className="text-xs text-gray-400">{gatewayStatus}</span>
          {isConnected && <span className="text-xs px-1.5 py-0.5 bg-purple-900 text-purple-300 rounded">OpenClaw</span>}
        </div>

        {screenshot ? (
          <img
            src={screenshot.startsWith('data:') ? screenshot : 'data:image/jpeg;base64,' + screenshot}
            alt="Browser"
            className="w-full h-full object-contain cursor-crosshair"
            onClick={handleScreenClick}
            draggable={false}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-gray-500 text-sm">{isConnected ? 'Loading browser...' : 'Connecting to OpenClaw Gateway...'}</p>
              <p className="text-gray-600 text-xs mt-1">{GATEWAY_URL}</p>
            </div>
          </div>
        )}
      </div>

      {!mobileTyping && (
        <div className="h-1.5 bg-gray-700 cursor-row-resize hover:bg-blue-600 active:bg-blue-500 transition-colors flex-shrink-0" onPointerDown={handleDividerPointerDown} style={{ touchAction: 'none' }} />
      )}
      {mobileTyping && <div className="h-px bg-gray-700 flex-shrink-0" />}

      <div className="flex-1 flex flex-col bg-gray-900 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
          <h2 className="text-sm font-semibold text-blue-400">Soalin</h2>
          <div className="flex items-center gap-1.5">
            <button onClick={() => { setChatMessages([{ role: 'system', content: 'Chat cleared.', timestamp: Date.now() }]) }} className="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition-colors text-gray-400">Clear</button>
            <button onClick={() => setCurrentView('settings')} className="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition-colors">Settings</button>
          </div>
        </div>

        {!mobileTyping && (
          <div className="flex gap-1 px-2 py-1 overflow-x-auto border-b border-gray-700 flex-shrink-0" style={{ backgroundColor: '#1a1d2e' }}>
            {quickActions.map((qa) => (
              <button key={qa.label} onClick={() => sendChatMessage(qa.cmd)} disabled={isLoading} className="flex-shrink-0 text-xs px-2.5 py-1 bg-gray-700 text-gray-300 rounded-full hover:bg-blue-600 hover:text-white transition-colors whitespace-nowrap disabled:opacity-50">{qa.label}</button>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
          {chatMessages.map((msg, i) => (
            <div key={i} className={'flex ' + (msg.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div className={'max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ' + (msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-md' : msg.role === 'system' ? 'bg-gray-700 text-gray-300 rounded-bl-md' : 'bg-gray-800 text-gray-200 rounded-bl-md')}>
                {msg.role === 'assistant' && (
                  <span className="text-xs font-medium block mb-0.5">
                    <span className="text-purple-400">OpenClaw</span>
                    {msg.streaming && <span className="text-blue-400 ml-1 animate-pulse">streaming...</span>}
                  </span>
                )}
                <span className="whitespace-pre-wrap">{msg.content}</span>
              </div>
            </div>
          ))}
          {isLoading && !streamingText && (
            <div className="flex justify-start">
              <div className="bg-gray-800 text-gray-400 px-3 py-2 rounded-2xl rounded-bl-md text-sm">
                <span className="text-xs text-purple-400 font-medium block mb-0.5">OpenClaw</span>
                <span className="inline-flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="flex-shrink-0 px-3 py-2 bg-gray-800 border-t border-gray-700">
          <div className="flex gap-2">
            <input ref={inputRef} type="text" value={inputText} onChange={e => setInputText(e.target.value)} onKeyDown={handleKeyDown} onFocus={() => setInputFocused(true)} onBlur={() => setTimeout(() => setInputFocused(false), 150)} placeholder="AI browser control..." className="flex-1 bg-gray-700 text-white text-sm px-4 py-2.5 rounded-full border border-gray-600 focus:border-blue-500 focus:outline-none placeholder-gray-500" disabled={isLoading} />
            <button onClick={sendMessage} disabled={isLoading || !inputText.trim()} className="px-4 py-2.5 bg-blue-600 text-white rounded-full text-sm font-medium hover:bg-blue-500 disabled:bg-gray-600 disabled:text-gray-400 transition-colors flex-shrink-0">Send</button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
