<script setup>
import { onMounted, ref } from 'vue'
import { fetchPatients } from './api'
import PatientList from './components/PatientList.vue'
import PatientDetail from './components/PatientDetail.vue'

const patients = ref([])
const loading = ref(true)
const error = ref('')
const selectedId = ref(idFromHash())

function idFromHash() {
  return Number(location.hash.slice(1)) || null
}

function onHashChange() {
  selectedId.value = idFromHash()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    patients.value = await fetchPatients()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('hashchange', onHashChange)
  load()
})
</script>

<template>
  <h1>Migrated patients</h1>

  <p v-if="loading">Loading patients...</p>
  <p v-else-if="error" class="error">
    {{ error }} <button @click="load">Retry</button>
  </p>
  <p v-else-if="!patients.length">
    No patients yet. Run <code>python manage.py import_fhir</code> in the backend first.
  </p>

  <div v-else class="columns">
    <PatientList :patients="patients" :selected-id="selectedId" />
    <PatientDetail v-if="selectedId" :patient-id="selectedId" />
    <p v-else>Select a patient to see their observations.</p>
  </div>
</template>

<style>
body {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 14px;
  margin: 20px;
}
.columns {
  display: flex;
  gap: 30px;
}
.error {
  color: red;
}
table {
  border-collapse: collapse;
}
th, td {
  border: 1px solid #ccc;
  padding: 4px 8px;
  text-align: left;
  vertical-align: top;
}
</style>
