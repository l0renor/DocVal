<script setup>
import { computed } from 'vue'

const props = defineProps({
  file: { type: Object, default: null },
})

const isImage = computed(() => props.file?.type?.startsWith('image/'))
const objectUrl = computed(() => (props.file ? URL.createObjectURL(props.file) : null))
</script>

<template>
  <v-sheet v-if="file" border rounded class="pa-2">
    <div class="text-caption mb-2">{{ file.name }}</div>
    <v-img v-if="isImage" :src="objectUrl" max-height="600" />
    <embed v-else :src="objectUrl" type="application/pdf" width="100%" height="600" />
  </v-sheet>
  <v-sheet v-else border rounded class="pa-4 text-medium-emphasis">
    Keine Vorschau
  </v-sheet>
</template>
