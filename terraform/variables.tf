variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "shipsafe-ai"
}

variable "region" {
  description = "Cloud Run region"
  type        = string
  default     = "us-central1"
}

variable "gemini_model" {
  description = "Vertex AI Gemini model ID"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "cloud_run_sa_email" {
  description = "Cloud Run service account email"
  type        = string
}

variable "image" {
  description = "Container image URI"
  type        = string
  default     = "gcr.io/shipsafe-ai/tidesync:latest"
}

variable "stale_threshold_seconds" {
  description = "Lag threshold in seconds before alerting"
  type        = number
  default     = 3600
}
