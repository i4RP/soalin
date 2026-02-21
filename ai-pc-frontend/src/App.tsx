import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const isMobile = () => /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || window.innerWidth < 768

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ChatEntry {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  usedLlm?: boolean
}

type View = 'main' | 'settings' | 'session'

function App() {
  const [screenshot, setScreenshot] = useState<string>('')
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([
    { role: 'system', content: 'Soalin へようこそ！チャットでPCを操作できます。例：「画面の中央をクリック」「Hello Worldと入力して」「Ctrl+Sを押して」', timestamp: Date.now() }
  ])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [screenRefreshRate, setScreenRefreshRate] = useState(1000)
  const [currentView, setCurrentView] = useState<View>('main')
  const [sessionId, setSessionId] = useState<string>('')
  const [connectionCode, setConnectionCode] = useState<string>('')
  const [codeInput, setCodeInput] = useState('')
  const [llmEnabled, setLlmEnabled] = useState(false)
  const [llmMode, setLlmMode] = useState('none')
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [anthropicKeyInput, setAnthropicKeyInput] = useState('')
  const [modelSelect, setModelSelect] = useState('gpt-4o')
  const [claudeModelSelect, setClaudeModelSelect] = useState('claude-sonnet-4-20250514')
  const [screenHeight, setScreenHeight] = useState(45)
  const [useWebSocket, setUseWebSocket] = useState(false)
  const [agentConnected, setAgentConnected] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null)
  const [inputFocused, setInputFocused] = useState(false)
  const [vpStyle, setVpStyle] = useState<{ height: number; top: number }>({ height: window.innerHeight, top: 0 })

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlCode = params.get('code')
    if (urlCode) {
      fetch(`${API_URL}/api/session/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: urlCode.trim() }),
      }).then(r => { if (r.ok) return r.json(); throw new Error() })
        .then(data => {
          setSessionId(data.session_id)
          setConnectionCode(data.connection_code)
        }).catch(() => {})
      return
    }
    const saved = localStorage.getItem('ai-pc-session')
    if (saved) {
      try {
        const data = JSON.parse(saved)
        if (data.sessionId) setSessionId(data.sessionId)
        if (data.connectionCode) setConnectionCode(data.connectionCode)
      } catch { /* ignore */ }
    }
  }, [])

  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('ai-pc-session', JSON.stringify({ sessionId, connectionCode }))
    }
  }, [sessionId, connectionCode])

  useEffect(() => {
    fetch(`${API_URL}/api/settings`).then(r => r.json()).then(d => {
      setLlmEnabled(d.llm_enabled)
      if (d.mode) setLlmMode(d.mode)
    }).catch(() => {})
  }, [])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }
    const wsUrl = API_URL.replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsUrl}/ws/screen`)
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'screen_update' && data.image) {
          setScreenshot(data.image)
          setIsConnected(true)
        }
      } catch { /* ignore */ }
    }
    ws.onclose = () => { setIsConnected(false) }
    ws.onerror = () => { setIsConnected(false) }
    wsRef.current = ws
  }, [])

  const checkAgentStatus = useCallback(async () => {
    if (!sessionId) return
    try {
      const res = await fetch(`${API_URL}/api/agent/status?session_id=${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setAgentConnected(data.connected)
      }
    } catch { /* ignore */ }
  }, [sessionId])

  useEffect(() => {
    if (sessionId) {
      checkAgentStatus()
      const interval = setInterval(checkAgentStatus, 3000)
      return () => clearInterval(interval)
    }
  }, [sessionId, checkAgentStatus])

  const fetchScreenshot = useCallback(async () => {
    try {
      const url = sessionId
        ? `${API_URL}/api/screenshot?session_id=${sessionId}`
        : `${API_URL}/api/screenshot`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setScreenshot(data.image)
        setIsConnected(true)
        if (data.source === 'remote_mac') setAgentConnected(true)
      } else {
        setIsConnected(false)
      }
    } catch {
      setIsConnected(false)
    }
  }, [sessionId])

  useEffect(() => {
    if (useWebSocket) {
      connectWebSocket()
      return () => { wsRef.current?.close() }
    } else {
      fetchScreenshot()
      const interval = setInterval(fetchScreenshot, screenRefreshRate)
      return () => clearInterval(interval)
    }
  }, [fetchScreenshot, screenRefreshRate, useWebSocket, connectWebSocket, sessionId])

  const createSession = async () => {
    try {
      const res = await fetch(`${API_URL}/api/session/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: '' }),
      })
      if (res.ok) {
        const data = await res.json()
        setSessionId(data.session_id)
        setConnectionCode(data.connection_code)
      }
    } catch { /* ignore */ }
  }

  const connectWithCode = async () => {
    if (!codeInput.trim()) return
    try {
      const res = await fetch(`${API_URL}/api/session/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: codeInput.trim() }),
      })
      if (res.ok) {
        const data = await res.json()
        setSessionId(data.session_id)
        setConnectionCode(data.connection_code)
        setCodeInput('')
        setCurrentView('main')
      }
    } catch { /* ignore */ }
  }

  const saveSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          openai_api_key: apiKeyInput,
          openai_model: modelSelect,
          anthropic_api_key: anthropicKeyInput,
          claude_model: claudeModelSelect,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setLlmEnabled(data.llm_enabled)
        if (data.mode) setLlmMode(data.mode)
        setCurrentView('main')
      }
    } catch { /* ignore */ }
  }

  const sendChatMessage = async (message: string) => {
    setChatMessages(prev => [...prev, { role: 'user', content: message, timestamp: Date.now() }])
    setIsLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      })
      if (res.ok) {
        const data = await res.json()
        setChatMessages(prev => [...prev, {
          role: 'assistant',
          content: data.reply,
          timestamp: Date.now(),
          usedLlm: data.used_llm,
        }])
        if (data.screenshot) setScreenshot(data.screenshot)
      } else {
        setChatMessages(prev => [...prev, { role: 'assistant', content: 'Error: サーバーからの応答に失敗しました', timestamp: Date.now() }])
      }
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: 'Error: サーバーに接続できません', timestamp: Date.now() }])
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
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
    { label: 'Click', cmd: 'クリック' },
    { label: 'W-Click', cmd: 'ダブルクリック' },
    { label: 'R-Click', cmd: '右クリック' },
    { label: 'Scroll Up', cmd: '上にスクロール' },
    { label: 'Scroll Down', cmd: '下にスクロール' },
    { label: 'Enter', cmd: 'Enterを押して' },
    { label: 'Esc', cmd: 'Escを押して' },
    { label: 'Ctrl+C', cmd: 'Ctrl+Cを押して' },
    { label: 'Ctrl+V', cmd: 'Ctrl+Vを押して' },
    { label: 'Ctrl+Z', cmd: 'Ctrl+Zを押して' },
    { label: 'Ctrl+S', cmd: 'Ctrl+Sを押して' },
    { label: 'All', cmd: '全選択' },
  ]

  const handleScreenClick = (e: React.MouseEvent<HTMLImageElement>) => {
    const img = e.currentTarget
    const rect = img.getBoundingClientRect()
    const scaleX = 1280 / rect.width
    const scaleY = 720 / rect.height
    const x = Math.round((e.clientX - rect.left) * scaleX)
    const y = Math.round((e.clientY - rect.top) * scaleY)
    sendChatMessage(`${x}, ${y}をクリック`)
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
          <button onClick={() => setCurrentView('main')} className="text-blue-400 text-sm mr-3">
            ← Back
          </button>
          <h2 className="text-sm font-semibold">Settings</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">AI Engine (Dual LLM)</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Status</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${llmEnabled ? (llmMode === 'dual' ? 'bg-purple-900 text-purple-300' : 'bg-green-900 text-green-300') : 'bg-gray-700 text-gray-400'}`}>
                  {llmEnabled ? (llmMode === 'dual' ? 'Dual AI' : llmMode === 'claude' ? 'Claude' : 'GPT-4o') : 'Regex Mode'}
                </span>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Anthropic API Key (Primary)</label>
                <input
                  type="password"
                  value={anthropicKeyInput}
                  onChange={e => setAnthropicKeyInput(e.target.value)}
                  placeholder="sk-ant-..."
                  className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Claude Model</label>
                <select
                  value={claudeModelSelect}
                  onChange={e => setClaudeModelSelect(e.target.value)}
                  className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                >
                  <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
                  <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                </select>
              </div>
              <div className="border-t border-gray-700 pt-3">
                <label className="text-xs text-gray-400 block mb-1">OpenAI API Key (Advisor)</label>
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={e => setApiKeyInput(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">GPT Model</label>
                <select
                  value={modelSelect}
                  onChange={e => setModelSelect(e.target.value)}
                  className="w-full bg-gray-700 text-white text-sm px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none"
                >
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4-turbo">GPT-4 Turbo</option>
                </select>
              </div>
              <button
                onClick={saveSettings}
                className="w-full py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-500 transition-colors"
              >
                Save
              </button>
              {llmEnabled && (
                <button
                  onClick={async () => {
                    await fetch(`${API_URL}/api/settings`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ openai_api_key: '', anthropic_api_key: '' }),
                    })
                    setLlmEnabled(false)
                    setLlmMode('none')
                    setApiKeyInput('')
                    setAnthropicKeyInput('')
                  }}
                  className="w-full py-2 bg-gray-700 text-gray-300 rounded text-sm hover:bg-gray-600 transition-colors"
                >
                  Disable LLM
                </button>
              )}
              <p className="text-xs text-gray-500">
                Dual AI: Claude generates actions, GPT-4o advises on failures. Both keys = maximum performance.
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">Screen Streaming</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">Mode</span>
                <button
                  onClick={() => setUseWebSocket(!useWebSocket)}
                  className={`text-xs px-3 py-1 rounded-full transition-colors ${useWebSocket ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}
                >
                  {useWebSocket ? 'WebSocket' : 'Polling'}
                </button>
              </div>
              {!useWebSocket && (
                <div className="flex items-center justify-between">
                  <span className="text-sm">Refresh Rate</span>
                  <div className="flex gap-1">
                    {[500, 1000, 2000].map(rate => (
                      <button
                        key={rate}
                        onClick={() => setScreenRefreshRate(rate)}
                        className={`text-xs px-2 py-1 rounded transition-colors ${screenRefreshRate === rate ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'}`}
                      >
                        {rate}ms
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">Session & PC Agent</h3>
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              {connectionCode ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Connection Code</span>
                    <span className="font-mono text-lg text-blue-400 tracking-widest">{connectionCode}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">PC Agent</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${agentConnected ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'}`}>
                      {agentConnected ? 'Connected' : 'Not Connected'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Screen Source</span>
                    <span className="text-xs text-gray-400">
                      {agentConnected ? 'Remote PC' : 'Virtual Desktop'}
                    </span>
                  </div>
                  {!agentConnected && (
                    <div className="bg-gray-900 rounded p-3 space-y-3">
                      <a
                        href={`${API_URL}/api/agent/download`}
                        className="block w-full py-2.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 transition-colors text-center"
                      >
                        PC Agent をダウンロード (Mac/Win/Linux)
                      </a>
                      <div className="text-xs text-gray-400 space-y-2">
                        <p className="font-medium text-gray-300">zipを解凍後、お使いのOSに合わせて実行:</p>
                        <details open className="border border-gray-700 rounded p-2">
                          <summary className="cursor-pointer hover:text-gray-300 font-medium text-gray-300">macOS</summary>
                          <div className="mt-1 space-y-1 pl-2">
                            <p className="font-medium text-gray-300">ターミナルで以下を実行:</p>
                            <code className="text-green-400 block bg-gray-950 p-2 rounded text-[11px] leading-relaxed whitespace-pre-wrap">
{`cd ~/Downloads/ai-pc-agent\nxattr -cr .\npip3 install -r requirements.txt\npython3 -m ai_pc_agent -s ${API_URL} -c ${connectionCode}`}
                            </code>
                            <p className="text-gray-500 mt-1">※ 事前に アクセシビリティ と 画面収録 の権限をターミナルに許可してください</p>
                            <p className="text-gray-500">（システム設定 → プライバシーとセキュリティ）</p>
                          </div>
                        </details>
                        <details className="border border-gray-700 rounded p-2">
                          <summary className="cursor-pointer hover:text-gray-300 font-medium text-gray-300">Windows</summary>
                          <div className="mt-1 space-y-0.5 pl-2">
                            <p>1. <code className="text-green-400">install_windows.bat</code> をダブルクリック</p>
                            <p>2. <code className="text-green-400">run_windows.bat</code> をダブルクリック</p>
                            <p>3. 接続コード <span className="text-blue-400 font-mono">{connectionCode}</span> を入力</p>
                          </div>
                        </details>
                        <details className="border border-gray-700 rounded p-2">
                          <summary className="cursor-pointer hover:text-gray-300 font-medium text-gray-300">Linux</summary>
                          <div className="mt-1 space-y-0.5 pl-2">
                            <p>1. <code className="text-green-400">chmod +x install_linux.sh run_linux.sh</code></p>
                            <p>2. <code className="text-green-400">./install_linux.sh</code> を実行</p>
                            <p>3. <code className="text-green-400">./run_linux.sh</code> を実行</p>
                            <p>4. 接続コード <span className="text-blue-400 font-mono">{connectionCode}</span> を入力</p>
                          </div>
                        </details>
                      </div>
                      <details className="text-xs text-gray-500">
                        <summary className="cursor-pointer hover:text-gray-300">手動コマンドで起動する場合</summary>
                        <code className="text-xs text-green-400 block bg-gray-950 p-2 rounded break-all mt-1">
                          python3 -m ai_pc_agent -s {API_URL} -c {connectionCode}
                        </code>
                      </details>
                    </div>
                  )}
                </>
              ) : (
                <button
                  onClick={createSession}
                  className="w-full py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-500 transition-colors"
                >
                  Create Session
                </button>
              )}
              <div>
                <label className="text-xs text-gray-400 block mb-1">Connect with Code</label>
                <div className="flex gap-2">
                  <input
                    value={codeInput}
                    onChange={e => setCodeInput(e.target.value.toUpperCase())}
                    placeholder="ABC123"
                    maxLength={6}
                    className="flex-1 bg-gray-700 text-white text-sm px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none font-mono tracking-widest text-center uppercase"
                  />
                  <button
                    onClick={connectWithCode}
                    className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-500 transition-colors"
                  >
                    Join
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">About</h3>
            <div className="bg-gray-800 rounded-lg p-4">
              <p className="text-sm text-gray-300">Soalin v4.0</p>
              <p className="text-xs text-gray-500 mt-1">Chat to control your PC with AI-powered natural language</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const mobileTyping = inputFocused && isMobile()

  return (
    <div className="flex flex-col bg-gray-950 text-white select-none" style={{ position: 'fixed', top: vpStyle.top, left: 0, right: 0, height: vpStyle.height, overflow: 'hidden' }}>
      <div className="relative flex-shrink-0 bg-black transition-all duration-200" style={{ height: mobileTyping ? `${vpStyle.height * screenHeight / 100}px` : `${screenHeight}vh` }}>
        <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
          {agentConnected && <span className="text-xs px-1.5 py-0.5 bg-green-900 text-green-300 rounded">PC</span>}
          {llmEnabled && <span className="text-xs px-1.5 py-0.5 bg-purple-900 text-purple-300 rounded">{llmMode === 'dual' ? 'Dual AI' : llmMode === 'claude' ? 'Claude' : 'LLM'}</span>}
        </div>
        {connectionCode && (
          <div className="absolute top-2 right-2 z-10">
            <span className="text-xs font-mono bg-gray-800 bg-opacity-80 px-2 py-1 rounded text-blue-400">{connectionCode}</span>
          </div>
        )}

        {screenshot ? (
          <img
            src={`data:image/${screenshot.startsWith('/9j/') ? 'jpeg' : 'png'};base64,${screenshot}`}
            alt="PC Screen"
            className="w-full h-full object-contain cursor-crosshair"
            onClick={handleScreenClick}
            draggable={false}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-gray-500 text-sm">Connecting to PC...</p>
            </div>
          </div>
        )}
      </div>

      {!mobileTyping && (
        <div
          className="h-1.5 bg-gray-700 cursor-row-resize hover:bg-blue-600 active:bg-blue-500 transition-colors flex-shrink-0"
          onPointerDown={handleDividerPointerDown}
          style={{ touchAction: 'none' }}
        />
      )}
      {mobileTyping && <div className="h-px bg-gray-700 flex-shrink-0" />}

      <div className="flex-1 flex flex-col bg-gray-900 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
          <h2 className="text-sm font-semibold text-blue-400">Soalin</h2>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setChatMessages([{ role: 'system', content: 'チャット履歴をクリアしました。', timestamp: Date.now() }])
              }}
              className="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition-colors text-gray-400"
            >
              Clear
            </button>
            <button
              onClick={() => setCurrentView('settings')}
              className="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition-colors"
            >
              Settings
            </button>
          </div>
        </div>

        {!mobileTyping && (
          <div className="flex gap-1 px-2 py-1 overflow-x-auto border-b border-gray-700 flex-shrink-0" style={{ backgroundColor: '#1a1d2e' }}>
            {quickActions.map((qa) => (
              <button
                key={qa.label}
                onClick={() => sendChatMessage(qa.cmd)}
                disabled={isLoading}
                className="flex-shrink-0 text-xs px-2.5 py-1 bg-gray-700 text-gray-300 rounded-full hover:bg-blue-600 hover:text-white transition-colors whitespace-nowrap disabled:opacity-50"
              >
                {qa.label}
              </button>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
          {chatMessages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : msg.role === 'system'
                    ? 'bg-gray-700 text-gray-300 rounded-bl-md'
                    : 'bg-gray-800 text-gray-200 rounded-bl-md'
                }`}
              >
                {msg.role === 'assistant' && (
                  <span className="text-xs font-medium block mb-0.5">
                    <span className="text-blue-400">AI</span>
                    {msg.usedLlm && <span className="text-purple-400 ml-1">LLM</span>}
                  </span>
                )}
                {msg.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 text-gray-400 px-3 py-2 rounded-2xl rounded-bl-md text-sm">
                <span className="text-xs text-blue-400 font-medium block mb-0.5">AI</span>
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
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setTimeout(() => setInputFocused(false), 150)}
              placeholder="AIにPCの操作を指示..."
              className="flex-1 bg-gray-700 text-white text-sm px-4 py-2.5 rounded-full border border-gray-600 focus:border-blue-500 focus:outline-none placeholder-gray-500"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !inputText.trim()}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-full text-sm font-medium hover:bg-blue-500 disabled:bg-gray-600 disabled:text-gray-400 transition-colors flex-shrink-0"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
