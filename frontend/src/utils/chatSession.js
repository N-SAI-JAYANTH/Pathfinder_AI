/**
 * Per-page chat session keys and local session id cache.
 */

export function resolvePageSession(context = {}, pathname = '') {
  if (context.pageType) {
    return {
      pageType: String(context.pageType).toLowerCase(),
      pageId: context.pageId != null ? String(context.pageId) : '',
    };
  }
  if (context.roadmapId != null) {
    return { pageType: 'roadmap', pageId: String(context.roadmapId) };
  }
  if (context.jobId != null) {
    return { pageType: 'job', pageId: String(context.jobId) };
  }
  if (pathname.includes('/roadmaps/')) {
    const id = pathname.split('/roadmaps/')[1]?.split('/')[0];
    if (id) return { pageType: 'roadmap', pageId: id };
  }
  if (pathname.includes('/jobs/')) {
    const id = pathname.split('/jobs/')[1]?.split('/')[0];
    if (id && id !== 'compare-jobs') return { pageType: 'job', pageId: id };
  }
  if (pathname.includes('/chat')) {
    return { pageType: 'global', pageId: 'advisor' };
  }
  return { pageType: 'global', pageId: '' };
}

export function sessionStorageKey(pageType, pageId) {
  return `pf_chat_session_${pageType}_${pageId || 'default'}`;
}

export function cacheSessionId(pageType, pageId, sessionId) {
  if (sessionId == null) return;
  try {
    localStorage.setItem(sessionStorageKey(pageType, pageId), String(sessionId));
  } catch {
    /* ignore quota */
  }
}

export function readCachedSessionId(pageType, pageId) {
  try {
    const v = localStorage.getItem(sessionStorageKey(pageType, pageId));
    return v ? parseInt(v, 10) : null;
  } catch {
    return null;
  }
}

export function toUiMessages(apiMessages) {
  if (!Array.isArray(apiMessages)) return [];
  return apiMessages
    .filter((m) => m && m.content && m.role !== 'system')
    .map((m, idx) => ({
      id: `${m.role}-${idx}-${m.content.slice(0, 12)}`,
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.content,
    }));
}
