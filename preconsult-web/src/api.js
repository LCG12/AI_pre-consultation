const BASE = '/api/preconsult'

async function request(path, options) {
  const response = await fetch(BASE + path, options)
  let data = null
  try {
    data = await response.json()
  } catch (e) {
    data = null
  }

  if (!response.ok) {
    const detail = data?.detail || data?.message || `请求失败 (${response.status})`
    throw new Error(detail)
  }

  return data
}

export async function fetchSessions() {
  return (await request('/sessions')).sessions
}

export async function fetchPaths() {
  return (await request('/paths')).paths
}

export async function createSession(pathId) {
  return request('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'web', path_id: pathId })
  })
}

export async function sendMessage(sessionId, text) {
  return request('/sessions/' + sessionId + '/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, asr_confidence: 0.95 })
  })
}

export async function getResult(sessionId) {
  return (await request('/sessions/' + sessionId + '/result')).state
}

export async function getMessages(sessionId) {
  return (await request('/sessions/' + sessionId + '/messages')).messages
}

export async function getDoctorSummary(sessionId) {
  return request('/sessions/' + sessionId + '/doctor-summary')
}
