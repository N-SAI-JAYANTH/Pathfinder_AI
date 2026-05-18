import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { aiAPI } from '../../services/api';
import {
  resolvePageSession,
  cacheSessionId,
  readCachedSessionId,
  toUiMessages,
} from '../../utils/chatSession';

const DEFAULT_WELCOME = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm your PathFinder AI Career Copilot. Ask me about this roadmap, jobs, or your career — I'll remember our conversation on this page.",
};

const ChatWidget = ({ context = {} }) => {
  const location = useLocation();
  const { pageType, pageId } = resolvePageSession(context, location.pathname);

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([DEFAULT_WELCOME]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(true);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadSession = useCallback(async () => {
    setSessionLoading(true);
    try {
      const res = await aiAPI.getChatSessionByPage(pageType, pageId);
      const data = res.data;
      setSessionId(data.id);
      cacheSessionId(pageType, pageId, data.id);
      const ui = toUiMessages(data.messages);
      setMessages(ui.length > 0 ? ui : [DEFAULT_WELCOME]);
    } catch (e) {
      console.warn('Could not load chat session', e);
      const cached = readCachedSessionId(pageType, pageId);
      if (cached) setSessionId(cached);
      setMessages([DEFAULT_WELCOME]);
    } finally {
      setSessionLoading(false);
    }
  }, [pageType, pageId]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const text = input.trim();
    const userMsg = { id: `u-${Date.now()}`, role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const payload = {
        message: text,
        session_id: sessionId || readCachedSessionId(pageType, pageId) || undefined,
        page_type: pageType,
        page_id: pageId,
        context: {
          ...context,
          roadmapId: context.roadmapId ?? (pageType === 'roadmap' ? pageId : undefined),
          jobId: context.jobId ?? (pageType === 'job' ? pageId : undefined),
        },
      };

      const response = await aiAPI.chat(payload);
      const data = response.data;

      if (data.session_id) {
        setSessionId(data.session_id);
        cacheSessionId(pageType, pageId, data.session_id);
      }

      const ui = toUiMessages(data.messages);
      if (ui.length > 0) {
        setMessages(ui);
      } else {
        setMessages((prev) => [
          ...prev,
          { id: `a-${Date.now()}`, role: 'assistant', content: data.response },
        ]);
      }
    } catch (error) {
      console.error('Chat failed', error);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: "Sorry, I'm having trouble connecting right now. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    if (!sessionId) {
      setMessages([DEFAULT_WELCOME]);
      return;
    }
    try {
      await aiAPI.clearChatSession(sessionId);
      await loadSession();
    } catch (e) {
      console.warn('Clear chat failed', e);
      setMessages([DEFAULT_WELCOME]);
    }
  };

  const placeholder =
    pageType === 'roadmap'
      ? 'Ask about this roadmap...'
      : pageType === 'job'
        ? 'Ask about this job...'
        : 'Ask about your career...';

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {isOpen && (
        <div className="mb-4 w-80 md:w-96 h-[28rem] glass-card flex flex-col shadow-2xl border border-cyan-500/30 overflow-hidden bg-[#0a0f1e]">
          <div className="p-3 bg-cyan-900/40 border-b border-cyan-500/20 flex justify-between items-center gap-2">
            <h3 className="font-bold text-cyan-300 flex items-center text-sm">
              <span className="mr-2">🤖</span> Career Copilot
            </h3>
            <div className="flex items-center gap-2">
              <button type="button" onClick={handleClear} className="text-xs text-slate-400 hover:text-cyan-300" title="Clear this page chat">
                Clear
              </button>
              <button type="button" onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white" aria-label="Close chat">
                ✕
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {sessionLoading ? (
              <p className="text-slate-400 text-sm text-center py-4">Loading conversation...</p>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-lg p-3 text-sm ${msg.role === 'user' ? 'bg-cyan-600/30 text-white border border-cyan-500/30' : 'bg-slate-700/50 text-slate-200 border border-slate-600/30'}`}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-700/50 rounded-lg p-3 text-sm text-slate-400">Typing...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="p-3 border-t border-cyan-500/20 bg-slate-900/50">
            <div className="flex gap-2">
              <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSend()} placeholder={placeholder} disabled={sessionLoading || loading} className="input-dark flex-1 px-3 py-2 text-sm" />
              <button type="button" onClick={handleSend} disabled={loading || sessionLoading || !input.trim()} className="btn-primary px-3 py-2 disabled:opacity-50">➤</button>
            </div>
          </div>
        </div>
      )}
      <button type="button" onClick={() => setIsOpen(!isOpen)} className="w-14 h-14 rounded-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-lg flex items-center justify-center text-2xl transition-transform hover:scale-105" aria-label={isOpen ? 'Close chat' : 'Open chat'}>
        {isOpen ? '✕' : '💬'}
      </button>
    </div>
  );
};

export default ChatWidget;
