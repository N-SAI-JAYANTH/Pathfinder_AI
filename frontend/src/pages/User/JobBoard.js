import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { jobAPI } from '../../services/api';
import { getErrorFromResponse } from '../../utils/errorHandler';

const JobBoard = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [selectedJobs, setSelectedJobs] = useState([]);

  const [filters, setFilters] = useState({
    keyword: '',
    location_city: '',
    location_country: '',
    remote_only: false,
    experience_level: [],
    job_type: [],
    work_type: [],
    min_salary: '',
    max_salary: '',
    industry: [],
    skills_required: [],
    posted_within: 'any',
    sort_by: 'newest',
  });

  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, [currentPage, filters]);

  const fetchJobs = async () => {
    setLoading(true);
    setError('');

    try {
      const params = {
        skip: currentPage * 20,
        limit: 20,
        keyword: filters.keyword || undefined,
        location_city: filters.location_city || undefined,
        location_country: filters.location_country || undefined,
        min_salary: filters.min_salary || undefined,
        max_salary: filters.max_salary || undefined,
        posted_within: filters.posted_within || 'any',
        sort_by: filters.sort_by || 'newest',
      };

      if (filters.remote_only) {
        params.remote_only = true;
      }
      if (filters.experience_level.length) {
        params.experience_level = filters.experience_level.join(',');
      }
      if (filters.job_type.length) {
        params.job_type = filters.job_type.join(',');
      }
      if (filters.work_type.length) {
        params.work_type = filters.work_type.join(',');
      }
      if (filters.industry.length) {
        params.industry = filters.industry.join(',');
      }
      if (filters.skills_required.length) {
        params.skills_required = filters.skills_required.join(',');
      }

      const response = await jobAPI.searchJobs(params);
      setJobs(response.data.jobs || []);
      setTotal(response.data.total || 0);
      setHasMore(response.data.has_more || false);
    } catch (err) {
      setError(getErrorFromResponse(err, 'Failed to fetch jobs'));
    } finally {
      setLoading(false);
    }
  };

  const toggleJobSelection = (jobId) => {
    setSelectedJobs(prev =>
      prev.includes(jobId) ? prev.filter(id => id !== jobId) : [...prev, jobId]
    );
  };

  const handleCompareJobs = () => {
    if (selectedJobs.length < 2) {
      alert('Please select at least 2 jobs to compare');
      return;
    }
    navigate(`/compare-jobs?jobs=${selectedJobs.join(',')}`);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setCurrentPage(0);
  };

  const handleMultiSelect = (key, value) => {
    setFilters(prev => {
      const current = prev[key] || [];
      const newValue = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value];
      return { ...prev, [key]: newValue };
    });
    setCurrentPage(0);
  };

  const clearFilters = () => {
    setFilters({
      keyword: '',
      location_city: '',
      location_country: '',
      remote_only: false,
      experience_level: [],
      job_type: [],
      work_type: [],
      min_salary: '',
      max_salary: '',
      industry: [],
      skills_required: [],
      posted_within: 'any',
      sort_by: 'newest',
    });
    setCurrentPage(0);
  };

  const formatSalary = (job) => {
    if (!job.is_salary_visible || (!job.min_salary && !job.max_salary)) {
      return 'Salary not disclosed';
    }

    const min = job.min_salary ? job.min_salary.toLocaleString() : '';
    const max = job.max_salary ? job.max_salary.toLocaleString() : '';
    const currency = job.salary_currency || 'INR';
    const period = job.salary_pay_period === 'year' ? 'yr' :
      job.salary_pay_period === 'month' ? 'mo' :
        job.salary_pay_period === 'hour' ? 'hr' : '';

    if (min && max) {
      return `${currency} ${min} - ${max} / ${period}`;
    } else if (min) {
      return `${currency} ${min}+ / ${period}`;
    } else if (max) {
      return `Up to ${currency} ${max} / ${period}`;
    }
    return 'Salary not disclosed';
  };

  const formatLocation = (job) => {
    const parts = [];
    if (job.location_city) parts.push(job.location_city);
    if (job.location_country) parts.push(job.location_country);
    if (job.is_remote) parts.push('Remote');
    if (parts.length === 0 && job.location) {
      return job.location;
    }
    return parts.length > 0 ? parts.join(', ') : 'Location not specified';
  };

  const experienceLevels = ['fresher', 'junior', 'mid', 'senior', 'lead'];
  const jobTypes = ['full_time', 'part_time', 'internship', 'contract', 'freelance'];
  const workTypes = ['onsite', 'remote', 'hybrid'];

  const FilterPill = ({ active, onClick, children }) => (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-sm font-medium transition-all duration-200 ${
        active
          ? 'bg-cyan-500 text-black shadow-lg shadow-cyan-500/25'
          : 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/20'
      }`}
    >
      {children}
    </button>
  );

  const JobCard = ({ job }) => (
    <div
      className="glass-card glass-card-hover p-6 relative overflow-hidden"
    >
      <div className="relative">
        <div className="flex justify-between items-start gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-2xl font-bold text-cyan-300 mb-2">
              {job.job_title || job.title || 'Untitled Job'}
            </h3>
            <p className="text-lg text-slate-300 mb-4">{job.company_name || 'Company Not Specified'}</p>

            <div className="flex flex-wrap gap-2 mb-4">
              <span className="flex items-center px-3 py-1 bg-cyan-500/10 text-cyan-200 border border-cyan-500/40 rounded-full text-sm font-medium">
                {formatLocation(job)}
              </span>
              <span className="flex items-center px-3 py-1 bg-cyan-500/10 text-cyan-200 border border-cyan-500/40 rounded-full text-sm font-medium">
                {job.job_type ? job.job_type.replace('_', ' ') : 'Full Time'}
              </span>
              {job.experience_level && (
                <span className="flex items-center px-3 py-1 bg-purple-500/20 text-purple-300 border border-purple-500/40 rounded-full text-sm font-medium">
                  {job.experience_level.charAt(0).toUpperCase() + job.experience_level.slice(1)}
                </span>
              )}
              {(job.is_salary_visible !== false) && (job.min_salary || job.max_salary || job.salary) && (
                <span className="flex items-center px-3 py-1 bg-green-500/20 text-green-300 border border-green-500/40 rounded-full text-sm font-medium">
                  {formatSalary(job)}
                </span>
              )}
            </div>

            <p className="text-slate-300 text-sm mb-4 line-clamp-2 leading-relaxed">
              {job.jd_text?.substring(0, 200) || job.description?.substring(0, 200) || 'No description available'}
              {(job.jd_text?.length > 200 || job.description?.length > 200) && '...'}
            </p>

            {job.skills_required && job.skills_required.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {Array.isArray(job.skills_required) ? (
                  <>
                    {job.skills_required.slice(0, 5).map((skill, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      >
                        {skill}
                      </span>
                    ))}
                    {job.skills_required.length > 5 && (
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-500/20 text-slate-300 border border-slate-500/40">
                        +{job.skills_required.length - 5} more
                      </span>
                    )}
                  </>
                ) : (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                    Skills: {typeof job.skills_required === 'string' ? job.skills_required : 'Not specified'}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col items-end gap-3 flex-shrink-0">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-400 hover:text-cyan-300 transition-colors">
              <input
                type="checkbox"
                checked={selectedJobs.includes(job.id)}
                onChange={() => toggleJobSelection(job.id)}
                className="w-5 h-5 rounded border-cyan-500/40 bg-black/40 text-cyan-500 focus:ring-cyan-500/50 focus:ring-offset-0"
                title="Select for comparison"
              />
              Compare
            </label>
            <Link
              to={`/jobs/${job.id}`}
              className="btn-primary px-6 py-2 text-sm font-medium whitespace-nowrap"
            >
              View Job
            </Link>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-slate-100">
      {/* Header */}
      <div className="relative overflow-hidden py-16">
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center px-4 py-2 glass-card rounded-full mb-6">
            <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse" />
            <span className="text-cyan-300 text-sm font-medium">Browse &amp; Filter Opportunities</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold text-cyan-100 mb-6">
            Search
            <span className="block bg-gradient-to-r from-cyan-300 to-cyan-400 bg-clip-text text-transparent">
              Jobs
            </span>
          </h1>
          <p className="text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
            Find your next role with keyword search, advanced filters, and side-by-side job comparison
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        {/* Search & Filters */}
        <div className="glass-card glass-card-hover p-6 mb-8">
          <div className="flex flex-col sm:flex-row gap-4 mb-4">
            <input
              type="text"
              placeholder="Search by title, company, or keywords..."
              value={filters.keyword}
              onChange={(e) => handleFilterChange('keyword', e.target.value)}
              className="input-dark flex-1 px-4 py-3"
            />
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="btn-secondary px-6 py-3 whitespace-nowrap"
            >
              {showFilters ? 'Hide Filters' : 'Show Filters'}
            </button>
          </div>

          {showFilters && (
            <div className="border-t border-cyan-500/20 pt-6 mt-2 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-cyan-300 mb-2">City</label>
                  <input
                    type="text"
                    value={filters.location_city}
                    onChange={(e) => handleFilterChange('location_city', e.target.value)}
                    placeholder="e.g., Bangalore"
                    className="input-dark w-full px-4 py-3"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Country</label>
                  <input
                    type="text"
                    value={filters.location_country}
                    onChange={(e) => handleFilterChange('location_country', e.target.value)}
                    placeholder="e.g., India"
                    className="input-dark w-full px-4 py-3"
                  />
                </div>
                <div className="flex items-end pb-1">
                  <label className="flex items-center cursor-pointer gap-2 text-sm font-medium text-cyan-300">
                    <input
                      type="checkbox"
                      checked={filters.remote_only}
                      onChange={(e) => handleFilterChange('remote_only', e.target.checked)}
                      className="w-5 h-5 rounded border-cyan-500/40 bg-black/40 text-cyan-500 focus:ring-cyan-500/50"
                    />
                    Remote Only
                  </label>
                </div>

                <div className="md:col-span-2 lg:col-span-3">
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Experience Level</label>
                  <div className="flex flex-wrap gap-2">
                    {experienceLevels.map(level => (
                      <FilterPill
                        key={level}
                        active={filters.experience_level.includes(level)}
                        onClick={() => handleMultiSelect('experience_level', level)}
                      >
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </FilterPill>
                    ))}
                  </div>
                </div>

                <div className="md:col-span-2 lg:col-span-3">
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Job Type</label>
                  <div className="flex flex-wrap gap-2">
                    {jobTypes.map(type => (
                      <FilterPill
                        key={type}
                        active={filters.job_type.includes(type)}
                        onClick={() => handleMultiSelect('job_type', type)}
                      >
                        {type.replace('_', ' ')}
                      </FilterPill>
                    ))}
                  </div>
                </div>

                <div className="md:col-span-2 lg:col-span-3">
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Work Type</label>
                  <div className="flex flex-wrap gap-2">
                    {workTypes.map(type => (
                      <FilterPill
                        key={type}
                        active={filters.work_type.includes(type)}
                        onClick={() => handleMultiSelect('work_type', type)}
                      >
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </FilterPill>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Min Salary</label>
                  <input
                    type="number"
                    value={filters.min_salary}
                    onChange={(e) => handleFilterChange('min_salary', e.target.value)}
                    placeholder="Min"
                    className="input-dark w-full px-4 py-3"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Max Salary</label>
                  <input
                    type="number"
                    value={filters.max_salary}
                    onChange={(e) => handleFilterChange('max_salary', e.target.value)}
                    placeholder="Max"
                    className="input-dark w-full px-4 py-3"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-cyan-300 mb-2">Sort By</label>
                  <select
                    value={filters.sort_by}
                    onChange={(e) => handleFilterChange('sort_by', e.target.value)}
                    className="input-dark w-full px-4 py-3"
                  >
                    <option value="newest">Newest First</option>
                    <option value="salary_high">Salary: High to Low</option>
                    <option value="relevance">Relevance</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-sm text-slate-400 hover:text-cyan-300 transition-colors"
                >
                  Clear All Filters
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/50 rounded-2xl p-6 mb-8 backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <svg className="h-6 w-6 text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <p className="text-red-300 font-medium">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="relative mb-6">
              <div className="w-20 h-20 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
            </div>
            <h3 className="text-xl font-semibold text-cyan-300 mb-2">Searching jobs...</h3>
            <p className="text-slate-400">Finding opportunities that match your criteria</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-6">
              <p className="text-slate-300">
                Found <span className="text-cyan-400 font-bold">{total}</span> jobs
              </p>
              {selectedJobs.length > 0 && (
                <p className="text-sm text-cyan-300">
                  {selectedJobs.length} selected for comparison
                </p>
              )}
            </div>

            {jobs.length > 0 ? (
              <div className="space-y-6">
                {jobs.map((job) => (
                  <JobCard key={job.id} job={job} />
                ))}
              </div>
            ) : (
              <div className="glass-card glass-card-hover p-12 text-center">
                <div className="w-24 h-24 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-cyan-500/40">
                  <svg className="w-12 h-12 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-cyan-300 mb-4">No jobs found</h3>
                <p className="text-slate-300 max-w-md mx-auto mb-6">
                  Try adjusting your search keywords or filters to see more results.
                </p>
                <button type="button" onClick={clearFilters} className="btn-primary px-8 py-3">
                  Clear Filters
                </button>
              </div>
            )}

            {/* Compare FAB */}
            {selectedJobs.length >= 2 && (
              <div className="fixed bottom-6 right-6 z-50">
                <button
                  type="button"
                  onClick={handleCompareJobs}
                  className="btn-primary px-6 py-4 rounded-full shadow-lg shadow-cyan-500/25 flex items-center gap-2 transform hover:scale-105"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  Compare {selectedJobs.length} Jobs
                </button>
              </div>
            )}

            {/* Pagination */}
            {total > 20 && (
              <div className="flex justify-center items-center gap-4 mt-10">
                <button
                  type="button"
                  onClick={() => setCurrentPage(prev => Math.max(0, prev - 1))}
                  disabled={currentPage === 0}
                  className="btn-secondary px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="text-slate-300 px-4">
                  Page <span className="text-cyan-400 font-semibold">{currentPage + 1}</span> of{' '}
                  <span className="text-cyan-400 font-semibold">{Math.ceil(total / 20)}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setCurrentPage(prev => prev + 1)}
                  disabled={!hasMore}
                  className="btn-secondary px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default JobBoard;
