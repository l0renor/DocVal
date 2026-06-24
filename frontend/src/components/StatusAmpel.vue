<script setup>
const props = defineProps({
  status: { type: String, required: true },
})

const AMPEL = {
  accepted: { color: 'green', label: 'Akzeptiert' },
  incomplete: { color: 'yellow', label: 'Unvollständig' },
  invalid_type: { color: 'red', label: 'Falscher Dokumenttyp' },
}

const ampel = AMPEL[props.status]
</script>

<template>
  <v-chip
    data-testid="ampel"
    :data-ampel="ampel.color"
    :color="ampel.color"
    label
  >
    {{ ampel.label }}
  </v-chip>
</template>
