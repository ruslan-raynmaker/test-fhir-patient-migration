export function patientName(patient) {
  const name = [patient.given_name, patient.family_name].filter(Boolean).join(' ')
  return name || `Patient ${patient.fhir_id}`
}

export function observationValue(obs) {
  if (obs.components.length) {
    return obs.components
      .map((c) => `${c.display || c.code}: ${c.value ?? '-'} ${c.unit}`.trim())
      .join(', ')
  }
  if (obs.value_number !== null) return `${obs.value_number} ${obs.value_unit}`.trim()
  return obs.value_text || '-'
}

export function formatDateTime(value) {
  return value ? new Date(value).toLocaleString() : '-'
}
