async function get(path) {
  let response
  try {
    response = await fetch(`/api${path}`)
  } catch {
    throw new Error('Could not reach the API. Is the backend running?')
  }
  if (response.status === 404) throw new Error('Not found')
  if (!response.ok) throw new Error(`API error (${response.status})`)
  return response.json()
}

export const fetchPatients = () => get('/patients/')
export const fetchPatient = (id) => get(`/patients/${id}/`)
