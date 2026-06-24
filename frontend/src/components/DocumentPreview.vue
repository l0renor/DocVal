<script setup>
import { computed } from 'vue'

const props = defineProps({
  file: { type: Object, default: null },
})

const isImage = computed(() => props.file?.type?.startsWith('image/'))
const objectUrl = computed(() => (props.file ? URL.createObjectURL(props.file) : null))
</script>

<template>
  <v-card v-if="file" variant="outlined">
    <v-card-item class="py-2">
      <template #prepend>
        <v-icon :icon="isImage ? 'mdi-image-outline' : 'mdi-file-pdf-box'" color="primary" />
      </template>
      <v-card-title class="text-body-2">{{ file.name }}</v-card-title>
    </v-card-item>
    <v-divider />
    <v-img v-if="isImage" :src="objectUrl" max-height="640" contain />
    <embed v-else :src="objectUrl" type="application/pdf" width="100%" height="640" />
  </v-card>

  <v-sheet
    v-else
    rounded="lg"
    border
    class="d-flex flex-column align-center justify-center text-medium-emphasis pa-10"
    min-height="240"
  >
    <v-icon icon="mdi-file-eye-outline" size="48" class="mb-2" />
    <span>Keine Vorschau</span>
  </v-sheet>
</template>
