import React, { useState, useRef, useEffect, useCallback } from 'react';
import { aiAPI } from '../../services/api';
import {
  resolvePageSession,
  cacheSessionId,
  readCachedSessionId,
  toUiMessages,
} from '../../utils/chatSession';

const PAGE = { pageType: 'global', pageId: 'advisor' };

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [newMessage, setNewMessage] = useState('');
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
      const res = await aiAPI.getChatSessionByPage(PAGE.pageType, PAGE.pageId);
      const data = res.data;
      setSessionId(data.id);
      cacheSessionId(PAGE.pageType, PAGE.pageId, data.id);
      const ui = toUiMessages(data.messages);
      setMessages(
        ui.map((m, i) => ({
          ...m,
          id: m.id || `${m.role}-${i}`,
          type: m.role === 'user' ? 'user' : 'bot',
          timestamp: new Date(),
        }))
      );
    } catch (e) {
      console.warn('Chat session load failed', e);
      const cached = readCachedSessionId(PAGE.pageType, PAGE.pageId);
      if (cached) setSessionId(cached);
    } finally {
      setSessionLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || loading || sessionLoading) return;

    const text = newMessage.trim();
    const userMessage = {
      id: Date.now(),
      type: 'user',
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setNewMessage('');
    setLoading(true);

    try {
      const response = await aiAPI.chat({
        message: text,
        session_id: sessionId || readCachedSessionId(PAGE.pageType, PAGE.pageId) || undefined,
        page_type: PAGE.pageType,
        page_id: PAGE.pageId,
        context: resolvePageSession({}, '/chat'),
      });

      const data = response.data;
      if (data.session_id) {
        setSessionId(data.session_id);
        cacheSessionId(PAGE.pageType, PAGE.pageId, data.session_id);
      }

      const ui = toUiMessages(data.messages);
      if (ui.length > 0) {
        setMessages(
          ui.map((m, i) => ({
            ...m,
            id: m.id || `${m.role}-${i}`,
            type: m.role === 'user' ? 'user' : 'bot',
            timestamp: new Date(),
          }))
        );
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            type: 'bot',
            role: 'assistant',
            content: data.response,
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          type: 'bot',
          content: 'Sorry, I encountered an error while processing your message. Please try again.',
          timestamp: new Date(),
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = async () => {
    if (!sessionId) {
      await loadSession();
      return;
    }
    try {
      await aiAPI.clearChatSession(sessionId);
      await loadSession();
    } catch (e) {
      console.warn('Clear failed', e);
    }
  };

  const suggestedQuestions = [
    'How can I improve my coding skills?',
    'What are trending technologies in data science?',
    'How do I prepare for software engineer interviews?',
    'What career path fits my skills?',
    'How can I transition to a tech career?',
    'What certifications are valuable in my field?',
  ];

  const handleSuggestedQuestion = (question) => {
    setNewMessage(question);
  };

  const formatMessage = (content) =>
    content.split('\n').map((line, index, arr) => (
      <span key={index}>
        {line}
        {index < arr.length - 1 && <br />}
      </span>
    ));

  const showSuggestions = messages.filter((m) => m.type === 'user').length === 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-slate-100">
      <div className="relative overflow-hidden py-12">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center px-4 py-2 glass-card rounded-full mb-6">
            <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse" />
            <span className="text-cyan-300 text-sm font-medium">AI Career Assistant</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-cyan-100 mb-4">
            Career
            <span className="block bg-gradient-to-r from-cyan-300 to-cyan-400 bg-clip-text text-transparent">
              Copilot
            </span>
          </h1>
          <p className="text-lg text-slate-300 max-w-2xl mx-auto">
            RAG-powered answers with memory — this chat is saved for this page only
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12 -mt-4 relative z-10">
        <div className="glass-card glass-card-hover overflow-hidden flex flex-col" style={{ height: '750px' }}>
          <div className="px-6 py-4 border-b border-cyan-500/20 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-cyan-300">Career Copilot</h2>
              <p className="text-sm text-slate-400">Session: global advisor · history + knowledge base</p>
            </div>
            <div className="flex items-center gap-3">
              <button type="button" onClick={handleClearChat} className="btn-secondary text-sm px-4 py-2">
                New chat
              </button>
              <div className="flex items-center text-green-300 text-sm">
                <div className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse" />
                Online
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {sessionLoading ? (
              <p className="text-center text-slate-400 py-8">Loading your conversation...</p>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-5 py-3 text-sm leading-relaxed ${
                      message.type === 'user'
                        ? 'bg-cyan-500/20 text-cyan-100 border border-cyan-500/40'
                        : message.isError
                          ? 'bg-red-500/10 text-red-200 border border-red-500/40'
                          : 'bg-slate-800/60 text-slate-200 border border-slate-600/40'
                    }`}
                  >
                    {formatMessage(message.content)}
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-800/60 rounded-2xl px-5 py-3 text-slate-400 text-sm border border-slate-600/40">
                  AI is thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {showSuggestions && !sessionLoading && (
            <div className="px-6 py-4 border-t border-cyan-500/20">
              <h3 className="text-sm font-semibold text-cyan-300 mb-3">Try asking:</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleSuggestedQuestion(question)}
                    className="text-left glass-card glass-card-hover px-3 py-2 text-sm text-slate-300 hover:text-cyan-200"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="px-6 py-4 border-t border-cyan-500/20">
            <form onSubmit={handleSendMessage} className="flex gap-3">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Ask me anything — I'll remember what we discussed..."
                className="input-dark flex-1 px-4 py-3"
                disabled={loading || sessionLoading}
              />
              <button
                type="submit"
                disabled={!newMessage.trim() || loading || sessionLoading}
                className="btn-primary px-6 py-3 disabled:opacity-50"
              >
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Chat;
