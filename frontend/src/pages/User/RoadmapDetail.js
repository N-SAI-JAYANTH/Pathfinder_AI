import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { roadmapAPI, phase2API } from '../../services/api';
import LoadingSpinner from '../../components/Common/LoadingSpinner';
import { getErrorFromResponse } from '../../utils/errorHandler';
import ChatWidget from '../../components/Common/ChatWidget';

const feedbackLabels = {
  complete: 'Complete',
  too_hard: 'Too Hard',
  too_easy: 'Too Easy',
  skip_regenerate: 'Skip & Regenerate',
};

const isTaskCompleted = (task) =>
  task?.completed === true || (task?.status || '').toLowerCase() === 'completed';

const isTaskSkipped = (task) =>
  task?.skipped === true ||
  (task?.status || '').toLowerCase() === 'skipped' ||
  task?.skipped_optional === true;

const canGiveFeedback = (task) => !isTaskCompleted(task) && !isTaskSkipped(task);

const RoadmapDetail = () => {
  const { id } = useParams();
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [regeneratingTask, setRegeneratingTask] = useState(null);
  const [expandedTasks, setExpandedTasks] = useState({});
  const [adaptationInfo, setAdaptationInfo] = useState(null);
  const [actionError, setActionError] = useState('');

  const toggleTask = (taskId) => {
    setExpandedTasks((prev) => ({
      ...prev,
      [taskId]: !prev[taskId],
    }));
  };

  useEffect(() => {
    fetchRoadmap();
  }, [id]);

  useEffect(() => {
    setAdaptationInfo(null);
    setActionError('');
  }, [id]);

  const runRecommendAndAdapt = async (taskId, feedbackType) => {
    const rid = parseInt(id, 10);
    const recRes = await phase2API.getRecommendation({
      roadmap_id: rid,
      task_id: taskId,
      job_id: roadmap.job_id,
      feedback_type: feedbackType,
    });
    const adaptRes = await phase2API.adaptRoadmap({
      roadmap_id: rid,
      task_id: taskId,
      decision_id: recRes.data.decision_id,
    });
    return { rec: recRes.data, adapt: adaptRes.data };
  };

  const applyCompleteResult = (adapt, rec) => {
    setRoadmap((prev) => ({
      ...prev,
      roadmap_data: adapt.updated_roadmap,
    }));
    const nextId = adapt.next_task_id;
    if (nextId) {
      setExpandedTasks((prev) => ({ ...prev, [nextId]: true }));
    }
    setAdaptationInfo({
      message: 'Task marked complete.',
      feedbackLabel: feedbackLabels.complete,
      rlAction: adapt.selected_action || rec?.selected_action || 'KEEP_NEXT_TASK',
      explanation:
        adapt.explanation ||
        'The completed task was not rewritten. Continue with the next task when ready.',
      isComplete: true,
    });
    console.log('[roadmap] complete', {
      feedback_type: 'complete',
      selected_action: adapt.selected_action,
      applied: adapt.applied,
      next_task_id: nextId,
    });
  };

  const applyAdaptResult = (adapt, rec, feedbackType) => {
    setRoadmap((prev) => ({
      ...prev,
      roadmap_data: adapt.updated_roadmap,
    }));
    const backendExplanation =
      (adapt.explanation && adapt.explanation.trim()) ||
      (rec?.reason && rec.reason.trim()) ||
      '';
    setAdaptationInfo({
      message: 'Roadmap adapted based on your feedback.',
      feedbackLabel: feedbackLabels[feedbackType] || feedbackType,
      rlAction: adapt.selected_action,
      explanation: backendExplanation || rec?.explanation || '',
      isComplete: false,
    });
    console.log('[roadmap] adapted', {
      feedback_type: feedbackType,
      selected_action: adapt.selected_action,
      applied: adapt.applied,
    });
  };

  const handleFeedback = async (task, feedbackType) => {
    const taskId = task.task_id || task.title;
    const rid = parseInt(id, 10);
    setActionError('');

    console.log('[roadmap] feedback click', {
      feedback_type: feedbackType,
      task_id: taskId,
      roadmap_id: rid,
    });

    setRegeneratingTask(taskId);

    try {
      const { rec, adapt } = await runRecommendAndAdapt(taskId, feedbackType);

      console.log('[roadmap] recommend', {
        feedback_type: feedbackType,
        selected_action: rec.selected_action,
        valid_actions: rec.valid_actions,
        decision_id: rec.decision_id,
      });
      console.log('[roadmap] adapt', {
        feedback_type: adapt.feedback_type,
        selected_action: adapt.selected_action,
        applied: adapt.applied,
        next_task_id: adapt.next_task_id,
      });

      await phase2API.logInteraction({
        task_id: taskId,
        action_type: feedbackType,
        roadmap_id: rid,
        job_id: roadmap.job_id,
      });

      if (feedbackType === 'complete') {
        applyCompleteResult(adapt, rec);
        return;
      }

      if (feedbackType === 'skip_regenerate' && !adapt.applied) {
        console.error('[roadmap] skip adapt not applied, falling back to regenerate');
        await handleRegenerateTask(task, 'skip');
        setAdaptationInfo(null);
        return;
      }

      applyAdaptResult(adapt, rec, feedbackType);
    } catch (err) {
      console.error('Adaptive roadmap flow failed', err);
      if (feedbackType === 'skip_regenerate') {
        try {
          await handleRegenerateTask(task, 'skip');
          setAdaptationInfo(null);
          return;
        } catch (regErr) {
          console.error('Regenerate fallback failed', regErr);
          const msg = getErrorFromResponse(regErr, 'Could not adapt or regenerate this task');
          setActionError(msg);
          alert(msg);
          return;
        }
      }
      const msg = getErrorFromResponse(err, 'Adaptive roadmap update failed');
      setActionError(msg);
      alert(msg);
    } finally {
      setRegeneratingTask(null);
    }
  };

  const handleRegenerateTask = async (task, feedbackType) => {
    const taskId = task.task_id || task.title;
    setRegeneratingTask(taskId);

    try {
      const response = await roadmapAPI.regenerateTask(id, taskId, feedbackType);
      const newTask = response.data.new_task;

      setRoadmap((prev) => {
        const newPhases = prev.roadmap_data.roadmap.phases.map((phase) => ({
          ...phase,
          tasks: phase.tasks.map((t) => {
            if (t.task_id === taskId || t.title === taskId) {
              return newTask;
            }
            return t;
          }),
        }));

        return {
          ...prev,
          roadmap_data: {
            ...prev.roadmap_data,
            roadmap: {
              ...prev.roadmap_data.roadmap,
              phases: newPhases,
            },
          },
        };
      });
    } catch (err) {
      console.error('Failed to regenerate task', err);
      alert('Failed to regenerate task. Please try again.');
    } finally {
      setRegeneratingTask(null);
    }
  };

  const fetchRoadmap = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await roadmapAPI.getSavedRoadmaps();
      const foundRoadmap = response.data.find((r) => r.id === parseInt(id, 10));
      if (foundRoadmap) {
        setRoadmap(foundRoadmap);
      } else {
        setError('Roadmap not found');
      }
    } catch (fetchErr) {
      setError(getErrorFromResponse(fetchErr, 'Failed to fetch roadmap'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !roadmap) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black flex items-center justify-center">
        <div className="text-center">
          <div className="glass-card glass-card-hover p-8 max-w-md">
            <h2 className="text-2xl font-bold text-red-300 mb-4">Roadmap Not Found</h2>
            <p className="text-red-200 mb-6">
              {typeof error === 'string' ? error : String(error || 'The roadmap you are looking for does not exist.')}
            </p>
            <Link to="/roadmaps" className="inline-block btn-primary px-6 py-3">
              Back to Roadmaps
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const roadmapData = roadmap.roadmap_data;

  return (
    <div className="min-h-screen bg-gradient-to-b from-black via-[#020617] to-black text-slate-100">
      <div className="relative overflow-hidden py-16">
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="inline-flex items-center px-4 py-2 glass-card rounded-full mb-4">
                <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse" />
                <span className="text-cyan-300 text-sm font-medium">Saved Roadmap</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold text-cyan-100 mb-4">
                {roadmap.title || roadmap.target_career || 'Learning Roadmap'}
              </h1>
              {roadmap.target_career && (
                <p className="text-xl text-slate-300 mb-6">{roadmap.target_career}</p>
              )}
            </div>
            <div className="ml-8">
              <Link
                to="/roadmaps"
                className="inline-flex items-center justify-center px-4 py-2 glass-card glass-card-hover text-cyan-300 border border-cyan-500/40 hover:border-cyan-400 rounded-xl transition-colors"
              >
                <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span>Back to Roadmaps</span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto py-12 px-4 sm:px-6 lg:px-8 -mt-8 relative z-10">
        {actionError && (
          <div className="mb-4 glass-card border border-red-500/40 p-4 text-sm text-red-200">
            {actionError}
          </div>
        )}
        {adaptationInfo && (
          <div
            className={`mb-6 glass-card p-4 text-sm ${
              adaptationInfo.isComplete
                ? 'border border-green-500/40'
                : 'border border-cyan-500/30'
            }`}
          >
            <p
              className={
                adaptationInfo.isComplete ? 'text-green-200 font-medium' : 'text-cyan-200 font-medium'
              }
            >
              {adaptationInfo.message}
            </p>
            <p className="text-slate-300 mt-2">
              <span className="text-slate-500">Feedback:</span> {adaptationInfo.feedbackLabel}
            </p>
            {!adaptationInfo.isComplete && (
              <p className="text-slate-300 mt-1">
                <span className="text-slate-500">RL Action:</span>{' '}
                <span className="font-mono text-xs text-cyan-300">{adaptationInfo.rlAction}</span>
              </p>
            )}
            {adaptationInfo.explanation ? (
              <p className="text-slate-400 mt-2 text-xs leading-relaxed">
                <span className="text-slate-500">Reason:</span> {adaptationInfo.explanation}
              </p>
            ) : null}
          </div>
        )}

        {roadmapData?.role_summary && (
          <div className="mb-8 glass-card glass-card-hover p-6">
            <h3 className="text-2xl font-bold text-cyan-300 mb-4">{roadmapData.role_summary.title}</h3>
            {roadmapData.role_summary.what_you_do?.length > 0 && (
              <div className="mb-4">
                <h4 className="text-lg font-semibold text-cyan-300 mb-2">Key Responsibilities:</h4>
                <ul className="list-disc list-inside space-y-1 text-slate-300">
                  {roadmapData.role_summary.what_you_do.map((item, idx) => (
                    <li key={idx} className="pb-0.5">{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {roadmapData.role_summary.required_stack && (
              <div>
                <h4 className="text-lg font-semibold text-cyan-300 mb-2">Required Tech Stack:</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(roadmapData.role_summary.required_stack).map(([category, skills]) =>
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

        {roadmapData?.gap_analysis && (
          <div className="mb-8 glass-card glass-card-hover p-6">
            <h3 className="text-2xl font-bold text-cyan-300 mb-4">Gap Analysis</h3>
            {roadmapData.gap_analysis.summary && (
              <p className="text-slate-300 mb-4 leading-relaxed pb-0.5">{roadmapData.gap_analysis.summary}</p>
            )}
            {roadmapData.gap_analysis.missing_skills?.length > 0 && (
              <div className="mb-4">
                <h4 className="text-lg font-semibold text-cyan-300 mb-2">Missing Skills:</h4>
                <div className="space-y-3">
                  {roadmapData.gap_analysis.missing_skills.map((skill, idx) => (
                    <div key={idx} className="glass-card glass-card-hover p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-cyan-300">{skill.skill}</span>
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium border ${
                            skill.priority === 'high'
                              ? 'bg-red-500/20 text-red-300 border-red-500/40'
                              : skill.priority === 'medium'
                                ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'
                                : 'bg-green-500/20 text-green-300 border-green-500/40'
                          }`}
                        >
                          {skill.priority} priority
                        </span>
                      </div>
                      {skill.reason && (
                        <p className="text-sm text-slate-300 mt-2 pb-0.5">{skill.reason}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {roadmapData?.roadmap?.phases?.length > 0 && (
          <div>
            <h3 className="text-2xl font-bold text-cyan-300 mb-6">Learning Phases</h3>
            <div className="space-y-6">
              {roadmapData.roadmap.phases.map((phase, phaseIdx) => (
                <div key={phase.phase_id || phaseIdx} className="glass-card glass-card-hover p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h4 className="text-xl font-bold text-cyan-300 mb-2">
                        Phase {phase.phase_id || phaseIdx + 1}: {phase.phase_name}
                      </h4>
                      {phase.goal && <p className="text-slate-300 mb-2 pb-0.5">{phase.goal}</p>}
                      {phase.estimated_duration_weeks && (
                        <span className="inline-block px-3 py-1 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded-full text-sm font-medium">
                          ~{phase.estimated_duration_weeks} weeks
                        </span>
                      )}
                    </div>
                  </div>
                  {phase.tasks?.length > 0 && (
                    <div className="space-y-4 mt-4">
                      {phase.tasks.map((task, taskIdx) => {
                        const taskId = task.task_id || task.title;
                        const isRegenerating = regeneratingTask === taskId;
                        const isExpanded = expandedTasks[taskId] || isRegenerating;
                        const completed = isTaskCompleted(task);
                        const skipped = isTaskSkipped(task);
                        const showFeedback = canGiveFeedback(task);

                        return (
                          <div
                            key={taskId || taskIdx}
                            className="glass-card glass-card-hover p-4 relative group transition-all duration-300"
                          >
                            {isRegenerating && (
                              <div className="absolute inset-0 bg-black/50 backdrop-blur-sm z-20 flex flex-col items-center justify-center rounded-xl">
                                <div className="w-8 h-8 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mb-2" />
                                <span className="text-cyan-300 text-sm font-medium animate-pulse">
                                  Updating roadmap...
                                </span>
                              </div>
                            )}

                            <div
                              className="flex items-center justify-between cursor-pointer"
                              onClick={() => toggleTask(taskId)}
                            >
                              <div className="flex items-center gap-2 flex-wrap">
                                <h5 className="text-lg font-semibold text-cyan-300">{task.title}</h5>
                                {completed && (
                                  <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-300 border border-green-500/40">
                                    Completed
                                  </span>
                                )}
                                {skipped && !completed && (
                                  <span className="px-2 py-0.5 text-xs rounded-full bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
                                    Skipped
                                  </span>
                                )}
                              </div>
                              <button
                                type="button"
                                className="p-1 rounded-full hover:bg-white/10 transition-colors flex-shrink-0"
                                aria-expanded={isExpanded}
                                aria-label={isExpanded ? 'Collapse task' : 'Expand task'}
                              >
                                <svg
                                  className={`w-6 h-6 text-cyan-400 transform transition-transform duration-300 ${
                                    isExpanded ? 'rotate-180' : ''
                                  }`}
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M19 9l-7 7-7-7"
                                  />
                                </svg>
                              </button>
                            </div>

                            <div
                              className={`mt-3 overflow-hidden transition-all duration-300 ${
                                isExpanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'
                              }`}
                            >
                              {task.description && (
                                <p className="text-slate-300 mb-3 pb-0.5 leading-relaxed border-l-2 border-cyan-500/30 pl-3">
                                  {task.description}
                                </p>
                              )}

                              {task.jd_alignment?.length > 0 && (
                                <div className="mb-3 mt-3">
                                  <span className="text-sm font-medium text-cyan-300">JD Alignment: </span>
                                  <ul className="list-disc list-inside text-sm text-slate-300 mt-1 space-y-1">
                                    {task.jd_alignment.map((align, idx) => (
                                      <li key={idx} className="pb-0.5">{align}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {task.subtasks?.length > 0 && (
                                <div className="mb-3">
                                  <span className="text-sm font-medium text-cyan-300">Subtasks:</span>
                                  <ul className="list-disc list-inside text-sm text-slate-300 mt-1 space-y-1">
                                    {task.subtasks.map((subtask, idx) => (
                                      <li key={idx} className="pb-0.5">{subtask}</li>
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

                              {showFeedback && (
                                <div className="mt-4 pt-4 border-t border-cyan-500/20 flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleFeedback(task, 'complete');
                                    }}
                                    className="px-3 py-1 bg-green-500/20 hover:bg-green-500/30 text-green-300 text-xs rounded border border-green-500/40 transition-colors"
                                    disabled={isRegenerating}
                                  >
                                    Complete
                                  </button>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleFeedback(task, 'too_hard');
                                    }}
                                    className="px-3 py-1 bg-orange-500/20 hover:bg-orange-500/30 text-orange-200 text-xs rounded border border-orange-500/40"
                                    disabled={isRegenerating}
                                  >
                                    Too Hard
                                  </button>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleFeedback(task, 'too_easy');
                                    }}
                                    className="px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 text-blue-200 text-xs rounded border border-blue-500/40"
                                    disabled={isRegenerating}
                                  >
                                    Too Easy
                                  </button>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleFeedback(task, 'skip_regenerate');
                                    }}
                                    className="px-3 py-1 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300 text-xs rounded border border-yellow-500/40"
                                    disabled={isRegenerating}
                                  >
                                    Skip &amp; Regenerate
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <ChatWidget context={{ roadmapId: id }} />
    </div>
  );
};

export default RoadmapDetail;
