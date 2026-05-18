import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { jobAPI, roadmapAPI } from '../../services/api';
import LoadingSpinner from '../../components/Common/LoadingSpinner';
import ChatWidget from '../../components/Common/ChatWidget';
import { getErrorFromResponse } from '../../utils/errorHandler';

const JobDetail = () => {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [roadmap, setRoadmap] = useState(null);
  const [savedRoadmapId, setSavedRoadmapId] = useState(null);
  const [loadingSavedRoadmap, setLoadingSavedRoadmap] = useState(true);
  const [generatingRoadmap, setGeneratingRoadmap] = useState(false);
  const [roadmapError, setRoadmapError] = useState('');
  const [savingRoadmap, setSavingRoadmap] = useState(false);
  const [roadmapSaved, setRoadmapSaved] = useState(false);

  useEffect(() => {
    fetchJobDetails();
    loadSavedRoadmap();
  }, [id]);

  const loadSavedRoadmap = async () => {
    setLoadingSavedRoadmap(true);
    try {
      const response = await roadmapAPI.getRoadmapByJob(id);
      const data = response.data;
      if (data?.roadmap_data) {
        setRoadmap(data.roadmap_data);
        setSavedRoadmapId(data.id);
        setRoadmapSaved(true);
      }
    } catch (err) {
      if (err.response?.status !== 404) {
        console.warn('Could not load saved roadmap:', err);
      }
    } finally {
      setLoadingSavedRoadmap(false);
    }
  };

  const fetchJobDetails = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await jobAPI.getJobById(id);
      setJob(response.data);
    } catch (err) {
      setError(getErrorFromResponse(err, 'Failed to fetch job details'));
    } finally {
      setLoading(false);
    }
  };

  const formatSalary = (j) => {
    if (!j) return 'Salary not disclosed';
    if (j.is_salary_visible === false || (!j.min_salary && !j.max_salary && !j.salary)) {
      return 'Salary not disclosed';
    }
    if (j.min_salary || j.max_salary) {
      const min = j.min_salary ? j.min_salary.toLocaleString() : '';
      const max = j.max_salary ? j.max_salary.toLocaleString() : '';
      const currency = j.salary_currency || 'INR';
      const period =
        j.salary_pay_period === 'year' ? 'yr' :
        j.salary_pay_period === 'month' ? 'mo' :
        j.salary_pay_period === 'hour' ? 'hr' : '';
      if (min && max) return `${currency} ${min} - ${max} / ${period}`;
      if (min) return `${currency} ${min}+ / ${period}`;
      if (max) return `Up to ${currency} ${max} / ${period}`;
    }
    if (j.salary) return j.salary;
    return 'Salary not disclosed';
  };

  const formatLocation = (j) => {
    if (!j) return 'Location not specified';
    const parts = [];
    if (j.location_city) parts.push(j.location_city);
    if (j.location_country) parts.push(j.location_country);
    if (j.is_remote) parts.push('Remote');
    if (parts.length === 0 && j.location) return j.location;
    return parts.length > 0 ? parts.join(', ') : 'Location not specified';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Not specified';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  const handleGenerateRoadmap = async () => {
    setGeneratingRoadmap(true);
    setRoadmapError('');

    try {
      const response = await jobAPI.generateJobRoadmapForUser(id);
      setRoadmap(response.data.roadmap);
      if (response.data.roadmap_id) {
        setSavedRoadmapId(response.data.roadmap_id);
        setRoadmapSaved(true);
      }
    } catch (err) {
      setRoadmapError(getErrorFromResponse(err, 'Failed to generate roadmap'));
    } finally {
      setGeneratingRoadmap(false);
    }
  };

  const handleSaveRoadmap = async () => {
    if (!roadmap || roadmapSaved || savingRoadmap) return;

    setSavingRoadmap(true);
    try {
      const title = roadmap.role_summary?.title || `${job.job_title} - Learning Roadmap`;
      const response = await roadmapAPI.saveRoadmap({
        roadmap_data: roadmap,
        title,
        job_id: parseInt(id, 10),
        roadmap_type: 'job',
        target_career: roadmap.role_summary?.title || job.job_title,
      });
      setSavedRoadmapId(response.data.id);
      setRoadmapSaved(true);
    } catch (err) {
      alert(getErrorFromResponse(err, 'Failed to save roadmap'));
    } finally {
      setSavingRoadmap(false);
    }
  };

  const priorityClass = (priority) => {
    if (priority === 'high') return 'bg-red-500/20 text-red-300 border-red-500/40';
    if (priority === 'medium') return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
    return 'bg-green-500/20 text-green-300 border-green-500/40';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center">
        <div className="text-center">
          <div className="glass-card glass-card-hover p-8 max-w-md">
            <h2 className="text-2xl font-bold text-red-300 mb-4">Job Not Found</h2>
            <p className="text-slate-300 mb-6">
              {typeof error === 'string' ? error : String(error || 'The job you are looking for does not exist.')}
            </p>
            <Link to="/jobs" className="btn-primary px-6 py-3 inline-flex items-center justify-center">
              <span>Back to Job Board</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-slate-100">
      {/* Hero */}
      <div className="relative overflow-hidden py-16">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            <div className="flex-1">
              <div className="inline-flex items-center px-4 py-2 glass-card rounded-full mb-4">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse" />
                <span className="text-cyan-300 text-sm font-medium">Job Opportunity</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold text-cyan-100 mb-4">
                {job.job_title || job.title || 'Job Title'}
              </h1>
              <p className="text-xl text-slate-300 mb-6">{job.company_name || 'Company Name'}</p>
              <div className="flex flex-wrap gap-3">
                <span className="px-4 py-2 bg-cyan-500/10 text-cyan-200 border border-cyan-500/40 rounded-full text-sm font-medium">
                  {formatLocation(job)}
                </span>
                <span className="px-4 py-2 bg-cyan-500/10 text-cyan-200 border border-cyan-500/40 rounded-full text-sm font-medium">
                  {job.job_type ? job.job_type.replace('_', ' ') : 'Full Time'}
                </span>
                {job.experience_level && (
                  <span className="px-4 py-2 bg-purple-500/20 text-purple-300 border border-purple-500/40 rounded-full text-sm font-medium">
                    {job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1)}
                  </span>
                )}
                {job.work_type && (
                  <span className="px-4 py-2 bg-cyan-500/10 text-cyan-200 border border-cyan-500/40 rounded-full text-sm font-medium">
                    {job.work_type.charAt(0).toUpperCase() + job.work_type.slice(1)}
                  </span>
                )}
              </div>
            </div>
            <Link
              to="/jobs"
              className="inline-flex items-center justify-center px-4 py-2 glass-card glass-card-hover text-cyan-300 border border-cyan-500/40 hover:border-cyan-400 rounded-xl transition-colors flex-shrink-0"
            >
              <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              <span>Back to Jobs</span>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main */}
          <div className="lg:col-span-2 space-y-6">
            <div className="glass-card glass-card-hover p-8">
              <h2 className="text-2xl font-bold text-cyan-300 mb-4 flex items-center">
                <div className="w-10 h-10 bg-cyan-500/20 border border-cyan-500/40 rounded-xl flex items-center justify-center mr-3">
                  <svg className="w-6 h-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                Job Description
              </h2>
              <div className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                {job.jd_text || job.description || 'No description available.'}
              </div>
            </div>

            {job.skills_required && (Array.isArray(job.skills_required) ? job.skills_required.length > 0 : true) && (
              <div className="glass-card glass-card-hover p-8">
                <h2 className="text-2xl font-bold text-cyan-300 mb-4 flex items-center">
                  <div className="w-10 h-10 bg-cyan-500/20 border border-cyan-500/40 rounded-xl flex items-center justify-center mr-3">
                    <svg className="w-6 h-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  Required Skills
                </h2>
                <div className="flex flex-wrap gap-3">
                  {Array.isArray(job.skills_required) ? (
                    job.skills_required.map((skill, index) => (
                      <span
                        key={index}
                        className="px-4 py-2 rounded-full text-sm font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      >
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="px-4 py-2 rounded-full text-sm font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                      {job.skills_required}
                    </span>
                  )}
                </div>
              </div>
            )}

            {job.nice_to_have_skills && Array.isArray(job.nice_to_have_skills) && job.nice_to_have_skills.length > 0 && (
              <div className="glass-card glass-card-hover p-8">
                <h2 className="text-2xl font-bold text-cyan-300 mb-4 flex items-center">
                  <div className="w-10 h-10 bg-green-500/20 border border-green-500/40 rounded-xl flex items-center justify-center mr-3">
                    <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  Nice to Have Skills
                </h2>
                <div className="flex flex-wrap gap-3">
                  {job.nice_to_have_skills.map((skill, index) => (
                    <span
                      key={index}
                      className="px-4 py-2 rounded-full text-sm font-medium bg-green-500/20 text-green-300 border border-green-500/40"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <div className="glass-card glass-card-hover p-6">
              <h3 className="text-xl font-bold text-cyan-300 mb-4 text-center">Apply Now</h3>

              {loadingSavedRoadmap ? (
                <div className="text-center text-slate-400 text-sm mb-4 py-3">Loading roadmap...</div>
              ) : (
                <>
                  {roadmap && roadmapSaved && (
                    <p className="text-green-300 text-sm text-center mb-3 border border-green-500/30 bg-green-500/10 rounded-lg px-3 py-2">
                      Roadmap saved for this job
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={handleGenerateRoadmap}
                    disabled={generatingRoadmap}
                    className="btn-primary w-full mb-4 px-6 py-4 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {generatingRoadmap ? (
                      <>
                        <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>{roadmap ? 'Regenerating...' : 'Generating Roadmap...'}</span>
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                        </svg>
                        <span>{roadmap ? 'Regenerate Learning Roadmap' : 'Generate Learning Roadmap'}</span>
                      </>
                    )}
                  </button>
                  {savedRoadmapId && (
                    <Link
                      to={`/roadmaps/${savedRoadmapId}`}
                      className="btn-secondary w-full mb-4 px-6 py-3 flex items-center justify-center gap-2 text-center"
                    >
                      Open saved roadmap
                    </Link>
                  )}
                </>
              )}

              {roadmapError && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-xl">
                  <p className="text-red-300 text-sm">{roadmapError}</p>
                </div>
              )}

              {job.application_url ? (
                <a
                  href={job.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary w-full flex items-center justify-center gap-2 mb-4"
                >
                  <span>Apply on Company Website</span>
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              ) : job.application_email ? (
                <a
                  href={`mailto:${job.application_email}?subject=Application for ${job.job_title || job.title}`}
                  className="btn-primary w-full flex items-center justify-center gap-2 mb-4"
                >
                  <span>Apply via Email</span>
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </a>
              ) : (
                <div className="text-center px-6 py-4 bg-slate-500/10 border border-slate-500/30 rounded-xl mb-4 text-slate-400 text-sm">
                  Application details not provided
                </div>
              )}

              <div className="space-y-4 pt-4 border-t border-cyan-500/20">
                {(job.is_salary_visible !== false) && (job.min_salary || job.max_salary || job.salary) && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Salary</div>
                    <div className="text-lg font-bold text-cyan-300">{formatSalary(job)}</div>
                  </div>
                )}
                {(job.min_experience_years || job.max_experience_years) && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Experience Required</div>
                    <div className="text-lg font-semibold text-cyan-300">
                      {job.min_experience_years && job.max_experience_years
                        ? `${job.min_experience_years} - ${job.max_experience_years} years`
                        : job.min_experience_years
                        ? `${job.min_experience_years}+ years`
                        : `Up to ${job.max_experience_years} years`}
                    </div>
                  </div>
                )}
                {job.industry && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Industry</div>
                    <div className="text-lg font-semibold text-cyan-300">{job.industry}</div>
                  </div>
                )}
                {job.employment_level && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Employment Level</div>
                    <div className="text-lg font-semibold text-cyan-300">
                      {job.employment_level.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </div>
                  </div>
                )}
                {job.application_deadline && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Application Deadline</div>
                    <div className="text-lg font-semibold text-cyan-300">{formatDate(job.application_deadline)}</div>
                  </div>
                )}
                {job.created_at && (
                  <div className="text-center">
                    <div className="text-sm font-medium text-slate-400 mb-1">Posted</div>
                    <div className="text-sm text-slate-300">{formatDate(job.created_at)}</div>
                  </div>
                )}
              </div>
            </div>

            <div className="glass-card glass-card-hover p-6 sticky top-20">
              <h3 className="text-lg font-bold text-cyan-300 mb-4 text-center">Job Summary</h3>
              <div className="space-y-3 text-slate-300 text-sm">
                <div className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2V6a2 2 0 012-2h4a2 2 0 012 2v2z" />
                  </svg>
                  <span>{job.job_type ? job.job_type.replace('_', ' ') : 'Full Time'}</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                  </svg>
                  <span>{job.experience_level ? job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1) : 'Any Level'}</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>{formatLocation(job)}</span>
                </div>
                {job.is_remote && (
                  <div className="flex items-center justify-center gap-2">
                    <svg className="w-5 h-5 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <span>Remote Work Available</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Generated Roadmap — dark theme matching RoadmapDetail */}
        {roadmap && (
          <div className="mt-8 space-y-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <h2 className="text-3xl font-bold text-cyan-300 flex items-center">
                <div className="w-12 h-12 bg-cyan-500/20 border border-cyan-500/40 rounded-xl flex items-center justify-center mr-4 flex-shrink-0">
                  <svg className="w-7 h-7 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                  </svg>
                </div>
                Your Personalized Learning Roadmap
              </h2>
              <div className="flex items-center gap-3 flex-shrink-0">
                {roadmapSaved ? (
                  <span className="px-4 py-2 rounded-xl font-semibold bg-green-500/20 text-green-300 border border-green-500/40 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Saved to your roadmaps
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleSaveRoadmap}
                    disabled={savingRoadmap}
                    className="btn-primary px-4 py-2 rounded-xl font-semibold flex items-center gap-2 disabled:opacity-50"
                  >
                    {savingRoadmap ? (
                      <>
                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Saving...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Save Roadmap
                      </>
                    )}
                  </button>
                )}
                {savedRoadmapId && (
                  <Link
                    to={`/roadmaps/${savedRoadmapId}`}
                    className="btn-secondary px-4 py-2 flex items-center justify-center"
                  >
                    Track progress
                  </Link>
                )}
              </div>
            </div>

            {roadmap.role_summary && (
              <div className="glass-card glass-card-hover p-6">
                <h3 className="text-2xl font-bold text-cyan-300 mb-4">{roadmap.role_summary.title}</h3>
                {roadmap.role_summary.what_you_do?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-lg font-semibold text-cyan-300 mb-2">Key Responsibilities:</h4>
                    <ul className="list-disc list-inside space-y-1 text-slate-300">
                      {roadmap.role_summary.what_you_do.map((item, idx) => (
                        <li key={idx} className="pb-0.5">{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {roadmap.role_summary.required_stack && (
                  <div>
                    <h4 className="text-lg font-semibold text-cyan-300 mb-2">Required Tech Stack:</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(roadmap.role_summary.required_stack).map(([category, skills]) =>
                        skills?.length > 0 ? (
                          <div key={category} className="mb-2 w-full">
                            <span className="text-sm font-medium text-cyan-300 capitalize block mb-1">
                              {category.replace('_', ' ')}:
                            </span>
                            <div className="flex flex-wrap gap-2">
                              {skills.map((skill, idx) => (
                                <span
                                  key={idx}
                                  className="px-3 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded-full text-sm"
                                >
                                  {skill}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {roadmap.gap_analysis && (
              <div className="glass-card glass-card-hover p-6">
                <h3 className="text-2xl font-bold text-cyan-300 mb-4">Gap Analysis</h3>
                {roadmap.gap_analysis.summary && (
                  <p className="text-slate-300 mb-4 leading-relaxed">{roadmap.gap_analysis.summary}</p>
                )}
                {roadmap.gap_analysis.missing_skills?.length > 0 && (
                  <div>
                    <h4 className="text-lg font-semibold text-cyan-300 mb-2">Missing Skills:</h4>
                    <div className="space-y-3">
                      {roadmap.gap_analysis.missing_skills.map((skill, idx) => (
                        <div key={idx} className="glass-card glass-card-hover p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium text-cyan-300">{skill.skill}</span>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${priorityClass(skill.priority)}`}>
                              {skill.priority} priority
                            </span>
                          </div>
                          {skill.reason && (
                            <p className="text-sm text-slate-300 mt-2">{skill.reason}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {roadmap.roadmap?.phases?.length > 0 && (
              <div>
                <h3 className="text-2xl font-bold text-cyan-300 mb-6">Learning Phases</h3>
                <div className="space-y-6">
                  {roadmap.roadmap.phases.map((phase, phaseIdx) => (
                    <div key={phase.phase_id || phaseIdx} className="glass-card glass-card-hover p-6">
                      <h4 className="text-xl font-bold text-cyan-300 mb-2">
                        Phase {phase.phase_id || phaseIdx + 1}: {phase.phase_name}
                      </h4>
                      {phase.goal && <p className="text-slate-300 mb-2">{phase.goal}</p>}
                      {phase.estimated_duration_weeks && (
                        <span className="inline-block px-3 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded-full text-sm font-medium">
                          ~{phase.estimated_duration_weeks} weeks
                        </span>
                      )}
                      {phase.tasks?.length > 0 && (
                        <div className="space-y-4 mt-4">
                          {phase.tasks.map((task, taskIdx) => (
                            <div key={task.task_id || taskIdx} className="glass-card glass-card-hover p-4">
                              <h5 className="text-lg font-semibold text-cyan-300 mb-2">{task.title}</h5>
                              {task.description && (
                                <p className="text-slate-300 mb-3 leading-relaxed border-l-2 border-cyan-500/30 pl-3">
                                  {task.description}
                                </p>
                              )}
                              {task.jd_alignment?.length > 0 && (
                                <div className="mb-3">
                                  <span className="text-sm font-medium text-cyan-300">JD Alignment: </span>
                                  <ul className="list-disc list-inside text-sm text-slate-300 mt-1 space-y-1">
                                    {task.jd_alignment.map((align, idx) => (
                                      <li key={idx}>{align}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {task.subtasks?.length > 0 && (
                                <div className="mb-3">
                                  <span className="text-sm font-medium text-cyan-300">Subtasks:</span>
                                  <ul className="list-disc list-inside text-sm text-slate-300 mt-1 space-y-1">
                                    {task.subtasks.map((subtask, idx) => (
                                      <li key={idx}>{subtask}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {task.skills_gained?.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-3">
                                  {task.skills_gained.map((skill, idx) => (
                                    <span
                                      key={idx}
                                      className="px-3 py-1 bg-green-500/20 text-green-300 border border-green-500/40 rounded-full text-xs"
                                    >
                                      {skill}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {task.status_options?.length > 0 && (
                                <p className="text-xs text-slate-500 mt-2">
                                  Save this roadmap to track progress and give feedback on tasks.
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <ChatWidget context={{ jobId: id, pageType: 'job', pageId: String(id) }} />
    </div>
  );
};

export default JobDetail;
