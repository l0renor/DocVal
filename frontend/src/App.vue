<script setup>
import { ref } from 'vue'
import { submitDocument } from '@/api/docverify.js'
import ResultsList from '@/components/ResultsList.vue'
import DocumentPreview from '@/components/DocumentPreview.vue'

const props = defineProps({
  baseUrl: { type: String, default: '/api' },
  // Injectable for tests; defaults to the real API client.
  submitFn: { type: Function, default: null },
})

const submit = props.submitFn || ((file) => submitDocument(file, { baseUrl: props.baseUrl }))

const selectedFile = ref(null)
const status = ref('idle') // idle | loading | done | error
const results = ref([])
const errorMessage = ref('')

async function onFileSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  selectedFile.value = file
  status.value = 'loading'
  errorMessage.value = ''
  results.value = []
  try {
    results.value = await submit(file)
    status.value = 'done'
  } catch (err) {
    errorMessage.value = err.message || 'Unbekannter Fehler'
    status.value = 'error'
  }
}
</script>

<template>
  <v-app>
    <v-app-bar title="DocVerify" flat density="comfortable" />
    <v-main>
      <v-container fluid>
        <v-row>
          <v-col cols="12" md="5">
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              aria-label="Dokument auswählen"
              @change="onFileSelected"
            />
            <DocumentPreview :file="selectedFile" class="mt-4" />
          </v-col>

          <v-col cols="12" md="7">
            <v-progress-circular v-if="status === 'loading'" indeterminate />

            <v-alert
              v-else-if="status === 'error'"
              type="error"
              variant="tonal"
              :text="errorMessage"
            />

            <ResultsList v-else-if="status === 'done'" :results="results" />

            <p v-else class="text-medium-emphasis">
              Noch kein Dokument geprüft — bitte ein Dokument auswählen.
            </p>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>
