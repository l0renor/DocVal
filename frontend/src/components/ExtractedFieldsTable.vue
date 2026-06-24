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

const LEGIBILITY = {
  legible: { color: 'success', label: 'lesbar' },
  partial: { color: 'warning', label: 'teilweise' },
  illegible: { color: 'error', label: 'unleserlich' },
}

function legibility(field) {
  return LEGIBILITY[field.legibility] || { color: 'grey', label: field.legibility }
}
</script>

<template>
  <v-table density="comfortable" class="fields-table">
    <thead>
      <tr>
        <th class="text-left">Feld</th>
        <th class="text-left">Wert</th>
        <th class="text-left">Lesbarkeit</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="field in fields"
        :key="field.name"
        :data-testid="`field-${field.name}`"
        :data-flagged="String(isFlagged(field))"
        :class="{ 'flagged-row': isFlagged(field) }"
      >
        <td class="font-weight-medium">{{ field.name }}</td>
        <td>
          <span :class="{ 'text-error font-italic': isMissing(field) }">
            {{ displayValue(field) }}
          </span>
          <v-icon
            v-if="isFlagged(field)"
            color="error"
            size="small"
            icon="mdi-alert"
            class="ms-1"
          />
        </td>
        <td>
          <v-chip :color="legibility(field).color" size="small" variant="tonal" label>
            {{ legibility(field).label }}
          </v-chip>
        </td>
      </tr>
    </tbody>
  </v-table>
</template>

<style scoped>
.flagged-row {
  background-color: rgba(198, 40, 40, 0.06);
}
</style>
