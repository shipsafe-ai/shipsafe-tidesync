# Grant Cloud Run SA access to existing secrets
resource "google_secret_manager_secret_iam_member" "fivetran_apikey" {
  secret_id = "FIVETRAN_APIKEY"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "fivetran_apisecret" {
  secret_id = "FIVETRAN_APISECRET"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "webhook_secret" {
  secret_id = "WEBHOOK_SECRET"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_sa_email}"
}
