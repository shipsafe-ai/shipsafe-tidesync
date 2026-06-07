resource "google_cloud_run_v2_service" "tidesync" {
  name     = "tidesync"
  location = var.region

  template {
    service_account = var.cloud_run_sa_email

    containers {
      image = var.image

      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = "shipsafe_hormuz"
      }
      env {
        name  = "FIVETRAN_ALLOW_WRITES"
        value = "false"
      }
      env {
        name  = "STALE_THRESHOLD_SECONDS"
        value = tostring(var.stale_threshold_seconds)
      }
      env {
        name  = "TIDESYNC_PUBLIC_URL"
        value = "https://tidesync-${var.project_id}-uc.a.run.app"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.tidesync.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "tidesync_url" {
  value = google_cloud_run_v2_service.tidesync.uri
}
