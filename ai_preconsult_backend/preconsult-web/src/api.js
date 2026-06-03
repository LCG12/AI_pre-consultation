const BASE = '/api/preconsult'

export async function fetchPaths() {
  const r = await fetch(BASE + '/paths')
  return (await r.json()).paths
}

export async function createSession(pathId) {
  const r = await fetch(BASE + '/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: 'web', path_id: pathId })
  })
  return r.json()
}

export async function sendMessage(sessionId, text) {
  const r = await fetch(BASE + '/sessions/' + sessionId + '/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, asr_confidence: 0.95 })
  })
  return r.json()
}

export async function getResult(sessionId) {
  const r = await fetch(BASE + '/sessions/' + sessionId + '/result')
  return (await r.json()).state
}

export async function getMessages(sessionId) {
  const r = await fetch(BASE + '/sessions/' + sessionId + '/messages')
  return (await r.json()).messages
}

export async function getDoctorSummary(sessionId) {
  const r = await fetch(BASE + '/sessions/' + sessionId + '/doctor-summary')
  return r.json()
}
