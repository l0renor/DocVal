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

async function onFileSelected(value) {
  const file = Array.isArray(value) ? value[0] : value
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
    <v-app-bar color="primary" flat>
      <template #prepend>
        <v-icon icon="mdi-file-document-check-outline" class="ms-2" />
      </template>
      <v-app-bar-title class="font-weight-bold">DocVerify</v-app-bar-title>
      <template #append>
        <span class="text-caption text-medium-emphasis me-4 d-none d-sm-inline">
          Prüf- und Extraktionsassistent
        </span>
      </template>
    </v-app-bar>

    <v-main class="bg-background">
      <v-container class="py-8">
        <v-row>
          <!-- Left: upload + preview -->
          <v-col cols="12" md="5">
            <v-card variant="elevated" elevation="2">
              <v-card-item>
                <template #prepend>
                  <v-icon icon="mdi-tray-arrow-up" color="primary" />
                </template>
                <v-card-title class="text-h6">Dokument prüfen</v-card-title>
                <v-card-subtitle>PDF, PNG oder JPG hochladen</v-card-subtitle>
              </v-card-item>
              <v-card-text>
                <v-file-input
                  label="Dokument auswählen"
                  accept="application/pdf,image/png,image/jpeg"
                  prepend-icon="mdi-paperclip"
                  :loading="status === 'loading'"
                  :disabled="status === 'loading'"
                  show-size
                  clearable
                  @update:model-value="onFileSelected"
                />
              </v-card-text>
            </v-card>

            <div class="mt-4">
              <DocumentPreview :file="selectedFile" />
            </div>
          </v-col>

          <!-- Right: results / states -->
          <v-col cols="12" md="7">
            <v-fade-transition mode="out-in">
              <div v-if="status === 'loading'" key="loading">
                <div class="d-flex align-center ga-3 mb-4">
                  <v-progress-circular indeterminate color="primary" size="24" />
                  <span class="text-body-1">Dokument wird geprüft …</span>
                </div>
                <v-skeleton-loader type="article, table" />
              </div>

              <v-alert
                v-else-if="status === 'error'"
                key="error"
                type="error"
                variant="tonal"
                prominent
                icon="mdi-alert-octagon"
                title="Prüfung fehlgeschlagen"
                :text="errorMessage"
              />

              <ResultsList
                v-else-if="status === 'done'"
                key="done"
                :results="results"
              />

              <v-sheet
                v-else
                key="empty"
                rounded="lg"
                border
                class="d-flex flex-column align-center justify-center text-medium-emphasis pa-12 text-center"
                min-height="320"
              >
                <v-icon icon="mdi-file-search-outline" size="64" class="mb-4" />
                <p class="text-body-1">
                  Noch kein Dokument geprüft — bitte ein Dokument auswählen.
                </p>
              </v-sheet>
            </v-fade-transition>
          </v-col>
        </v-row>
      </v-container>
    </v-main>
  </v-app>
</template>
