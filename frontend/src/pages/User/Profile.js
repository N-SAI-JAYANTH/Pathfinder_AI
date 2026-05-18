import React, { useState, useEffect } from 'react';
import { userAPI } from '../../services/api';
import LoadingSpinner from '../../components/Common/LoadingSpinner';
import { getErrorFromResponse } from '../../utils/errorHandler';

const Profile = () => {
  const [profile, setProfile] = useState({
    degree: '',
    course: '',
    cgpa_10th: '',
    cgpa_12th: '',
    total_cgpa: '',
    skills: [],
    extracted_skills: [],
    certifications: [],
    achievements: [],
    career_interests: []
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [newSkill, setNewSkill] = useState('');
  const [newCertification, setNewCertification] = useState('');
  const [newAchievement, setNewAchievement] = useState('');
  const [newInterest, setNewInterest] = useState('');

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const response = await userAPI.getProfile();
      setProfile(response.data);
      setIsEditing(false);
    } catch (error) {
      if (error.response?.status === 404) {
        setIsEditing(true);
      } else {
        setError('Failed to load profile');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const addArrayItem = (field, value, setter) => {
    if (value.trim()) {
      setProfile(prev => ({
        ...prev,
        [field]: [...prev[field], value.trim()]
      }));
      setter('');
    }
  };

  const removeArrayItem = (field, index) => {
    setProfile(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      if (profile.id) {
        await userAPI.updateProfile(profile);
        setSuccess('Profile updated successfully!');
      } else {
        const response = await userAPI.createProfile(profile);
        setProfile(response.data);
        setSuccess('Profile created successfully!');
      }
      setIsEditing(false);
    } catch (error) {
      setError(getErrorFromResponse(error, 'Failed to save profile'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center">
        <div className="text-center">
          <div className="relative">
            <div className="w-20 h-20 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-6"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full opacity-20 animate-pulse"></div>
            </div>
          </div>
          <h3 className="text-xl font-semibold text-cyan-300 mb-2">Loading your profile...</h3>
          <p className="text-slate-300">Setting up your career journey</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-slate-100">
      {/* Hero Section */}
      <div className="relative overflow-hidden py-16">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="inline-flex items-center px-4 py-2 glass-card rounded-full mb-6">
              <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse"></div>
              <span className="text-cyan-300 text-sm font-medium">Career Profile Management</span>
            </div>
            
            <h1 className="text-4xl md:text-6xl font-bold text-cyan-100 mb-6">
              Your Professional
              <span className="block bg-gradient-to-r from-cyan-300 to-cyan-400 bg-clip-text text-transparent">
                Profile
              </span>
            </h1>
            <p className="text-xl text-slate-300 max-w-3xl mx-auto leading-relaxed">
              Build and manage your comprehensive career profile to unlock personalized AI-powered recommendations
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        <div className="glass-card glass-card-hover overflow-hidden">
          <div className="px-8 py-8">
            <div className="flex justify-between items-center mb-8">
              <div className="flex items-center">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl flex items-center justify-center mr-4">
                  <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" />
                  </svg>
                </div>
                <div>
                  <h2 className="text-3xl font-bold text-cyan-300">Profile Details</h2>
                  <p className="text-slate-300 mt-1">Manage your academic and professional information</p>
                </div>
              </div>
              {!isEditing && profile.id && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="group flex items-center justify-center btn-primary px-6 py-3"
                >
                  <svg className="w-5 h-5 group-hover:rotate-12 transition-transform duration-200 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  <span>Edit Profile</span>
                </button>
              )}
            </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 mb-6 shadow-lg backdrop-blur-sm">
              <div className="flex items-center">
                <div className="w-8 h-8 bg-red-500/20 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-red-300 font-medium">
                  {typeof error === 'string' ? error : String(error || 'An error occurred')}
                </span>
              </div>
            </div>
          )}

          {success && (
            <div className="bg-green-500/10 border border-green-500/50 rounded-xl p-4 mb-6 shadow-lg backdrop-blur-sm">
              <div className="flex items-center">
                <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-green-300 font-medium">
                  {typeof success === 'string' ? success : String(success || 'Success')}
                </span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Basic Information Section */}
            <div className="glass-card glass-card-hover p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-cyan-300">Academic Information</h3>
              </div>
              
              {/* Degree and Course - Separate Boxes */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 mb-6">
                <div>
                  <label className="block text-sm font-semibold text-cyan-300 mb-2">
                    Degree
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="degree"
                      value={profile.degree || ''}
                      onChange={handleChange}
                      className="input-dark block w-full px-4 py-3"
                      placeholder="e.g., B.Tech, B.E., B.Sc."
                      style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                    />
                  ) : (
                    <div className="input-dark block w-full px-4 py-3 bg-black/40 border border-cyan-500/40 rounded-xl">
                      <span className="text-cyan-300 text-lg font-semibold">
                        {profile.degree || 'Not provided'}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold text-cyan-300 mb-2">
                    Course
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      name="course"
                      value={profile.course || ''}
                      onChange={handleChange}
                      className="input-dark block w-full px-4 py-3"
                      placeholder="e.g., Computer Science, Mechanical Engineering"
                      style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                    />
                  ) : (
                    <div className="input-dark block w-full px-4 py-3 bg-black/40 border border-cyan-500/40 rounded-xl">
                      <span className="text-cyan-300 text-lg font-semibold">
                        {profile.course || 'Not provided'}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* CGPA Fields - Three in a Row */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
                <div>
                  <label className="block text-sm font-semibold text-cyan-300 mb-2">
                    CGPA 10th
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      step="0.01"
                      name="cgpa_10th"
                      value={profile.cgpa_10th || ''}
                      onChange={handleChange}
                      className="input-dark block w-full px-4 py-3"
                      placeholder="e.g., 9.5"
                      style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                    />
                  ) : (
                    <div className="input-dark block w-full px-4 py-3 bg-black/40 border border-cyan-500/40 rounded-xl">
                      <span className="text-cyan-300 text-lg font-semibold">
                        {profile.cgpa_10th || 'Not provided'}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold text-cyan-300 mb-2">
                    CGPA 12th
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      step="0.01"
                      name="cgpa_12th"
                      value={profile.cgpa_12th || ''}
                      onChange={handleChange}
                      className="input-dark block w-full px-4 py-3"
                      placeholder="e.g., 8.9"
                      style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                    />
                  ) : (
                    <div className="input-dark block w-full px-4 py-3 bg-black/40 border border-cyan-500/40 rounded-xl">
                      <span className="text-cyan-300 text-lg font-semibold">
                        {profile.cgpa_12th || 'Not provided'}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-semibold text-cyan-300 mb-2">
                    Total CGPA
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      step="0.01"
                      name="total_cgpa"
                      value={profile.total_cgpa || ''}
                      onChange={handleChange}
                      className="input-dark block w-full px-4 py-3"
                      placeholder="e.g., 8.5"
                      style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                    />
                  ) : (
                    <div className="input-dark block w-full px-4 py-3 bg-black/40 border border-cyan-500/40 rounded-xl">
                      <span className="text-cyan-300 text-lg font-semibold">
                        {profile.total_cgpa || 'Not provided'}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Extracted Resume Skills Section */}
            {profile.extracted_skills && profile.extracted_skills.length > 0 && (
              <div className="glass-card glass-card-hover p-6">
                <div className="flex items-center mb-6">
                  <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-emerald-600 rounded-lg flex items-center justify-center mr-3">
                    <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <h3 className="text-xl font-bold text-cyan-300">Extracted Resume Skills</h3>
                    <p className="text-sm text-slate-400 mt-1">Skills automatically extracted from your uploaded resume</p>
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-3">
                  {profile.extracted_skills.map((skill, index) => (
                    <span
                      key={index}
                      className="group inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-green-500/20 to-emerald-500/20 text-green-300 border border-green-500/40 hover:shadow-lg hover:border-green-400 transition-all duration-200"
                    >
                      <svg className="w-4 h-4 mr-2 text-green-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span>{skill}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Skills Section */}
            <div className="glass-card glass-card-hover p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-cyan-300">Technical Skills</h3>
              </div>
              
              <div className="flex flex-wrap gap-3 mb-4">
                {profile.skills && profile.skills.length > 0 ? (
                  profile.skills.map((skill, index) => (
                    <span
                      key={index}
                      className="group inline-flex items-center px-4 py-2 rounded-full text-sm font-semibold bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/40 hover:shadow-lg hover:border-cyan-400 transition-all duration-200"
                    >
                      <svg className="w-4 h-4 mr-2 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="text-cyan-300">{skill}</span>
                      {isEditing && (
                        <button
                          type="button"
                          onClick={() => removeArrayItem('skills', index)}
                          className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition-colors duration-200"
                        >
                          ×
                        </button>
                      )}
                    </span>
                  ))
                ) : (
                  <p className="text-slate-400 text-sm">No skills added yet. Add skills manually or upload a resume to extract skills automatically.</p>
                )}
              </div>
              
              {isEditing && (
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={newSkill}
                    onChange={(e) => setNewSkill(e.target.value)}
                    className="bg-black/30 backdrop-blur-sm border border-cyan-500/30 rounded-xl text-cyan-100 placeholder:text-slate-400 px-4 py-3 flex-1 focus:ring-2 focus:ring-cyan-500/80 focus:border-cyan-400 outline-none transition-all"
                    placeholder="Add a technical skill (e.g., Python, JavaScript)"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addArrayItem('skills', newSkill, setNewSkill))}
                    style={{ color: '#cffafe', WebkitTextFillColor: '#cffafe' }}
                  />
                  <button
                    type="button"
                    onClick={() => addArrayItem('skills', newSkill, setNewSkill)}
                    className="btn-primary px-6 py-3"
                  >
                    <span>Add</span>
                  </button>
                </div>
              )}
            </div>

            {/* Certifications Section */}
            <div className="glass-card glass-card-hover p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-cyan-300">Certifications</h3>
              </div>
              
              <div className="space-y-3 mb-4">
                {profile.certifications.map((cert, index) => (
                  <div
                    key={index}
                    className="group flex items-center justify-between p-4 glass-card glass-card-hover"
                  >
                    <div className="flex items-center">
                      <div className="w-6 h-6 bg-gradient-to-r from-orange-400 to-yellow-500 rounded-lg flex items-center justify-center mr-3">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      </div>
                      <span className="text-cyan-200 font-medium">{cert}</span>
                    </div>
                    {isEditing && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem('certifications', index)}
                        className="px-3 py-1 bg-red-500/20 text-red-300 border border-red-500/40 rounded-lg hover:bg-red-500/30 transition-colors duration-200 font-medium"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              {isEditing && (
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={newCertification}
                    onChange={(e) => setNewCertification(e.target.value)}
                    className="input-dark flex-1 px-4 py-3"
                    placeholder="Add a certification (e.g., AWS Certified, Google Cloud)"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addArrayItem('certifications', newCertification, setNewCertification))}
                    style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                  />
                  <button
                    type="button"
                    onClick={() => addArrayItem('certifications', newCertification, setNewCertification)}
                    className="btn-primary px-6 py-3"
                  >
                    <span>Add</span>
                  </button>
                </div>
              )}
            </div>

            {/* Achievements Section */}
            <div className="glass-card glass-card-hover p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-cyan-300">Achievements</h3>
              </div>
              
              <div className="space-y-3 mb-4">
                {profile.achievements.map((achievement, index) => (
                  <div
                    key={index}
                    className="group flex items-center justify-between p-4 glass-card glass-card-hover"
                  >
                    <div className="flex items-center">
                      <div className="w-6 h-6 bg-gradient-to-r from-indigo-400 to-purple-500 rounded-lg flex items-center justify-center mr-3">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <span className="text-cyan-200 font-medium">{achievement}</span>
                    </div>
                    {isEditing && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem('achievements', index)}
                        className="px-3 py-1 bg-red-500/20 text-red-300 border border-red-500/40 rounded-lg hover:bg-red-500/30 transition-colors duration-200 font-medium"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              {isEditing && (
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={newAchievement}
                    onChange={(e) => setNewAchievement(e.target.value)}
                    className="input-dark flex-1 px-4 py-3"
                    placeholder="Add an achievement (e.g., Winner of Hackathon 2023)"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addArrayItem('achievements', newAchievement, setNewAchievement))}
                    style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                  />
                  <button
                    type="button"
                    onClick={() => addArrayItem('achievements', newAchievement, setNewAchievement)}
                    className="btn-primary px-6 py-3"
                  >
                    <span>Add</span>
                  </button>
                </div>
              )}
            </div>

            {/* Career Interests Section */}
            <div className="glass-card glass-card-hover p-6">
              <div className="flex items-center mb-6">
                <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center mr-3">
                  <svg className="w-5 h-5 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-cyan-300">Career Interests</h3>
              </div>
              
              <div className="flex flex-wrap gap-3 mb-4">
                {profile.career_interests.map((interest, index) => (
                  <span
                    key={index}
                    className="group inline-flex items-center px-4 py-2 rounded-xl text-sm font-semibold bg-gradient-to-r from-pink-100 to-rose-100 text-pink-800 border border-pink-200 hover:shadow-lg transition-all duration-200"
                  >
                    <svg className="w-4 h-4 mr-2 text-pink-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {interest}
                    {isEditing && (
                      <button
                        type="button"
                        onClick={() => removeArrayItem('career_interests', index)}
                        className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition-colors duration-200"
                      >
                        ×
                      </button>
                    )}
                  </span>
                ))}
              </div>
              
              {isEditing && (
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={newInterest}
                    onChange={(e) => setNewInterest(e.target.value)}
                    className="input-dark flex-1 px-4 py-3"
                    placeholder="Add a career interest (e.g., Data Science, Web Development)"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addArrayItem('career_interests', newInterest, setNewInterest))}
                    style={{ color: '#ffffff', WebkitTextFillColor: '#ffffff' }}
                  />
                  <button
                    type="button"
                    onClick={() => addArrayItem('career_interests', newInterest, setNewInterest)}
                    className="btn-primary px-6 py-3"
                  >
                    <span>Add</span>
                  </button>
                </div>
              )}
            </div>

            {isEditing && (
              <div className="flex justify-end space-x-4 pt-8 border-t border-cyan-500/20">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="btn-secondary group flex items-center justify-center px-6 py-3"
                  disabled={saving}
                >
                  <svg className="w-5 h-5 group-hover:-translate-x-1 transition-transform duration-200 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  <span>Cancel</span>
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary group flex items-center justify-center px-8 py-3 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                >
                  {saving ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 group-hover:scale-110 transition-transform duration-200 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span>Save Profile</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;