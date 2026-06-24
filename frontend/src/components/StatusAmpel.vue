<script setup>
const props = defineProps({
  status: { type: String, required: true },
})

// `key` is the semantic Ampel signal (green/yellow/red); `color` is the themed
// Vuetify colour used to render it.
const AMPEL = {
  accepted: { key: 'green', color: 'success', label: 'Akzeptiert', icon: 'mdi-check-circle' },
  incomplete: { key: 'yellow', color: 'warning', label: 'Unvollständig', icon: 'mdi-alert-circle' },
  invalid_type: { key: 'red', color: 'error', label: 'Falscher Dokumenttyp', icon: 'mdi-close-circle' },
}

const ampel = AMPEL[props.status]
</script>

<template>
  <v-chip
    data-testid="ampel"
    :data-ampel="ampel.key"
    :color="ampel.color"
    variant="flat"
    size="large"
    label
  >
    <v-icon start :icon="ampel.icon" />
    {{ ampel.label }}
  </v-chip>
</template>
