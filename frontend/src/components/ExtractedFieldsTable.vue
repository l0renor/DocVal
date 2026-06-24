<script setup>
defineProps({
  fields: { type: Array, default: () => [] },
})

function isMissing(field) {
  return field.value === null || field.value === undefined || field.value === ''
}

// A field is flagged for the Sachbearbeiter when it is missing a value or the
// model judged it not fully legible — these are the fields needing a manual look.
function isFlagged(field) {
  return isMissing(field) || field.legibility !== 'legible'
}

function displayValue(field) {
  return isMissing(field) ? 'fehlt' : field.value
}
</script>

<template>
  <v-table density="comfortable">
    <thead>
      <tr>
        <th>Feld</th>
        <th>Wert</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="field in fields"
        :key="field.name"
        :data-testid="`field-${field.name}`"
        :data-flagged="String(isFlagged(field))"
        :class="{ 'text-red': isFlagged(field) }"
      >
        <td>{{ field.name }}</td>
        <td>
          {{ displayValue(field) }}
          <v-icon v-if="isFlagged(field)" color="red" size="small" icon="mdi-alert" />
        </td>
      </tr>
    </tbody>
  </v-table>
</template>
