import axios from 'axios';
import { API_BASE_URL } from '../constants';

const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  registerUser: (userData) => api.post('/api/auth/register-user', userData),
  registerRecruiter: (recruiterData) => api.post('/api/auth/register-recruiter', recruiterData),
  login: (credentials) => {
    const formData = new FormData();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);
    return api.post('/api/auth/login', formData);
  },
};

export const userAPI = {
  getProfile: () => api.get('/api/user/profile'),
  createProfile: (profileData) => api.post('/api/user/profile', profileData),
  updateProfile: (profileData) => api.put('/api/user/profile', profileData),
  uploadResume: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/user/upload-resume', formData);
  },
};

export const jobAPI = {
  getAllJobs: (skip = 0, limit = 50) => api.get(`/api/jobs?skip=${skip}&limit=${limit}`),
  createJob: (jobData) => api.post('/api/recruiter/jobs', jobData),
  createJobEnhanced: (jobData) => api.post('/api/jobs/create', jobData), // New enhanced endpoint
  searchJobs: (filters) => {
    const params = new URLSearchParams();
    Object.keys(filters).forEach(key => {
      if (filters[key] !== null && filters[key] !== undefined && filters[key] !== '') {
        params.append(key, filters[key]);
      }
    });
    return api.get(`/api/jobs/search?${params.toString()}`);
  },
  getJobById: (jobId) => api.get(`/api/jobs/${jobId}`),
  generateJobRoadmap: (jobId) => api.post(`/api/jobs/${jobId}/generate-roadmap`), // For recruiters
  generateJobRoadmapForUser: (jobId) => api.post(`/api/jobs/${jobId}/generate-roadmap-for-user`), // For users
  getRecruiterJobs: () => api.get('/api/recruiter/jobs'),
  updateJob: (jobId, jobData) => api.put(`/api/recruiter/jobs/${jobId}`, jobData),
  deleteJob: (jobId) => api.delete(`/api/recruiter/jobs/${jobId}`),
};

export const aiAPI = {
  recommendCareers: () => api.post('/api/ai/recommend-careers'),
  matchJobs: () => api.post('/api/ai/match-jobs'),
  skillGapAnalysis: () => api.post('/api/ai/skill-gap-analysis'),
  strengthsWeaknesses: () => api.post('/api/ai/strengths-weaknesses'),
  chat: (payload) => api.post('/api/ai/chat', payload),
  getChatSessionByPage: (pageType, pageId = '') =>
    api.get('/api/ai/chat/sessions/by-page', { params: { page_type: pageType, page_id: pageId } }),
  getChatSession: (sessionId) => api.get(`/api/ai/chat/sessions/${sessionId}`),
  listChatSessions: () => api.get('/api/ai/chat/sessions'),
  clearChatSession: (sessionId) => api.delete(`/api/ai/chat/sessions/${sessionId}`),
};

export const roadmapAPI = {
  saveRoadmap: (roadmapData) => api.post('/api/roadmaps/save', roadmapData),
  getRoadmapByJob: (jobId) => api.get(`/api/roadmaps/by-job/${jobId}`),
  getSavedRoadmaps: () => api.get('/api/roadmaps'),
  deleteRoadmap: (roadmapId) => api.delete(`/api/roadmaps/${roadmapId}`),
  regenerateTask: (roadmapId, taskId, feedbackType, rating) => api.post(`/api/roadmaps/${roadmapId}/tasks/${taskId}/regenerate`, { feedback_type: feedbackType, rating }),
};

export const phase2API = {
  logInteraction: (data) => api.post('/api/phase2/interactions/log', data),
  /** Query params: roadmap_id, task_id, job_id, feedback_type (optional), forced_action (debug only). */
  getRecommendation: (params = {}) =>
    api.get('/api/phase2/recommend', { params }),
  /** Body: { roadmap_id, task_id, decision_id } — decision_id from getRecommendation. */
  adaptRoadmap: (body) => api.post('/api/phase2/roadmap/adapt', body),
  queryRag: (query) => api.post('/api/phase2/rag/query', null, { params: { query } }),
};

export default api;