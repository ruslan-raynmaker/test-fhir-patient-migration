<script setup>
import { ref, watch } from 'vue'
import { fetchPatient } from '../api'
import { formatDateTime, observationValue, patientName } from '../format'

const props = defineProps({
  patientId: { type: Number, required: true },
})

const patient = ref(null)
const loading = ref(false)
const error = ref('')

async function load(id) {
  loading.value = true
  error.value = ''
  patient.value = null
  try {
    const data = await fetchPatient(id)
    // user may have clicked another patient while this one was loading
    if (id === props.patientId) patient.value = data
  } catch (e) {
    if (id === props.patientId) error.value = e.message
  } finally {
    if (id === props.patientId) loading.value = false
  }
}

watch(() => props.patientId, load, { immediate: true })
</script>

<template>
  <div>
    <p v-if="loading">Loading...</p>
    <p v-else-if="error" class="error">
      {{ error }} <button @click="load(patientId)">Retry</button>
    </p>

    <template v-else-if="patient">
      <h2>{{ patientName(patient) }}</h2>
      <p>
        FHIR id: {{ patient.fhir_id }}<br />
        Gender: {{ patient.gender || '?' }}<br />
        Birth date: {{ patient.birth_date || '?' }}
      </p>

      <p v-if="!patient.observations.length">No observations for this patient.</p>
      <table v-else>
        <thead>
          <tr>
            <th>Date</th>
            <th>Observation</th>
            <th>Value</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="obs in patient.observations" :key="obs.id">
            <td>{{ formatDateTime(obs.effective_at) }}</td>
            <td>{{ obs.display || obs.code || '-' }}</td>
            <td>{{ observationValue(obs) }}</td>
            <td>{{ obs.status }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
