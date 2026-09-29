<script setup>
import { patientName } from '../format'

defineProps({
  patients: { type: Array, required: true },
  selectedId: { type: Number, default: null },
})
</script>

<template>
  <ul>
    <li v-for="patient in patients" :key="patient.id">
      <a :href="'#' + patient.id" :class="{ selected: patient.id === selectedId }">
        <b>{{ patientName(patient) }}</b>
        <span>{{ patient.gender || '?' }} · {{ patient.birth_date || 'no DOB' }} · {{ patient.observation_count }} obs</span>
      </a>
    </li>
  </ul>
</template>

<style scoped>
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  width: 320px;
  flex-shrink: 0;
}
a {
  display: block;
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 3px;
  margin-bottom: 4px;
  color: inherit;
  text-decoration: none;
}
a:hover {
  background: #f5f5f5;
}
a.selected {
  background: #e8e8e8;
  border-color: #999;
}
span {
  display: block;
  color: #666;
  font-size: 12px;
}
</style>
