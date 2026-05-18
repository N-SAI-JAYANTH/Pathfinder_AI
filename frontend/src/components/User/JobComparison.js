import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { jobAPI } from '../../services/api';
import LoadingSpinner from '../Common/LoadingSpinner';

const JobComparison = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const jobIds = searchParams.get('jobs')?.split(',') || [];
    if (jobIds.length === 0) {
      setError('No jobs selected for comparison');
      setLoading(false);
      return;
    }
    fetchJobs(jobIds);
  }, [searchParams]);

  const fetchJobs = async (jobIds) => {
    setLoading(true);
    const fetchedJobs = [];
    
    for (const id of jobIds) {
      try {
        const response = await jobAPI.getJobById(id);
        fetchedJobs.push(response.data);
      } catch (err) {
        console.error(`Failed to fetch job ${id}:`, err);
      }
    }
    
    setJobs(fetchedJobs);
    setLoading(false);
  };

  const formatSalary = (job) => {
    if (!job.is_salary_visible || (!job.min_salary && !job.max_salary)) return 'Not disclosed';
    const currency = job.salary_currency || 'INR';
    const min = job.min_salary?.toLocaleString() || '';
    const max = job.max_salary?.toLocaleString() || '';
    return min && max ? `${currency} ${min} - ${max}` : min ? `${currency} ${min}+` : `Up to ${currency} ${max}`;
  };

  if (loading) return <LoadingSpinner />;

  if (error || jobs.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center p-4">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-4">{error || 'No jobs to compare'}</h2>
          <button onClick={() => navigate('/jobs')} className="px-6 py-3 bg-cyan-500 text-black font-semibold rounded-full hover:bg-cyan-400">
            Back to Jobs
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-4xl font-bold" style={{ color: 'cyan', textShadow: '0 0 10px cyan' }}>Job Comparison</h1>
          <button onClick={() => navigate('/jobs')} className="px-4 py-2 bg-cyan-500 text-black rounded-full hover:bg-cyan-400">
            Back to Jobs
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="border border-cyan-500/30 p-4 bg-black/60 backdrop-blur-sm text-left" style={{ color: 'cyan' }}>Attribute</th>
                {jobs.map((job) => (
                  <th key={job.id} className="border border-cyan-500/30 p-4 bg-black/60 backdrop-blur-sm" style={{ color: 'cyan' }}>
                    <div className="font-bold text-lg mb-2">{job.job_title}</div>
                    <div className="text-sm font-normal">{job.company_name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Match Score */}
              {jobs.some(j => j.match_score) && (
                <tr>
                  <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Match Score</td>
                  {jobs.map((job) => (
                    <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40 text-center">
                      {job.match_score ? (
                        <span className={`px-4 py-2 rounded-full font-bold ${job.match_score >= 80 ? 'bg-green-500/20 text-green-400' : job.match_score >= 60 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>
                          {job.match_score}%
                        </span>
                      ) : <span className="text-gray-500">N/A</span>}
                    </td>
                  ))}
                </tr>
              )}

              {/* Location */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Location</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40" style={{ color: 'white' }}>
                    {job.location_city}, {job.location_country}
                    {job.is_remote && <span className="ml-2 px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-sm">Remote</span>}
                  </td>
                ))}
              </tr>

              {/* Work Type */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Work Type</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40 capitalize" style={{ color: 'white' }}>
                    {job.work_type || 'Not specified'}
                  </td>
                ))}
              </tr>

              {/* Experience Level */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Experience</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40 capitalize" style={{ color: 'white' }}>
                    {job.experience_level || 'Any'}
                    {(job.min_experience_years || job.max_experience_years) && (
                      <div className="text-sm text-gray-400">
                        {job.min_experience_years && job.max_experience_years 
                          ? `${job.min_experience_years}-${job.max_experience_years} years`
                          : job.min_experience_years 
                          ? `${job.min_experience_years}+ years`
                          : `Up to ${job.max_experience_years} years`}
                      </div>
                    )}
                  </td>
                ))}
              </tr>

              {/* Salary */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Salary</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40" style={{ color: 'white' }}>
                    {formatSalary(job)}
                  </td>
                ))}
              </tr>

              {/* Industry */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Industry</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40" style={{ color: 'white' }}>
                    {job.industry || 'Not specified'}
                  </td>
                ))}
              </tr>

              {/* Required Skills */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold align-top" style={{ color: 'cyan' }}>Required Skills</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40">
                    <div className="flex flex-wrap gap-2">
                      {(job.skills_required || []).map((skill, idx) => (
                        <span key={idx} className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-sm">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </td>
                ))}
              </tr>

              {/* Actions */}
              <tr>
                <td className="border border-cyan-500/30 p-4 bg-black/40 font-semibold" style={{ color: 'cyan' }}>Actions</td>
                {jobs.map((job) => (
                  <td key={job.id} className="border border-cyan-500/30 p-4 bg-black/40 text-center">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="inline-block px-4 py-2 bg-cyan-500 text-black rounded-full hover:bg-cyan-400 font-semibold"
                    >
                      View Details
                    </Link>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default JobComparison;
