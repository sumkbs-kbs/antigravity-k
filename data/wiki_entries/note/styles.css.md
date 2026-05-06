---
id: 199
category: note
tags: []
created: 2026-05-04T09:42:52.668313
---

# styles.css

```css
/* NanoBanana PRO - Obsidian Plugin Styles */

/* ==================== Progress Modal ==================== */
.nanobanana-progress-modal {
  padding: 20px;
  min-width: 400px;
}

.nanobanana-progress-title {
  text-align: center;
  margin-bottom: 20px;
  font-size: 1.4em;
}

.nanobanana-progress-container {
  background: var(--background-modifier-border);
  border-radius: 8px;
  height: 24px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}

.nanobanana-progress-bar {
  background: linear-gradient(90deg, var(--interactive-accent), var(--interactive-accent-hover));
  height: 100%;
  width: 0%;
  transition: width 0.3s ease;
  border-radius: 8px;
}

.nanobanana-progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-weight: bold;
  font-size: 0.9em;
  color: var(--text-normal);
}

.nanobanana-steps-container {
  margin-bottom: 20px;
}

.nanobanana-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 4px 0;
  border-radius: 6px;
  background: var(--background-secondary);
  transition: all 0.2s ease;
}

.nanobanana-step.active {
  background: var(--background-modifier-hover);
  border-left: 3px solid var(--interactive-accent);
}

.nanobanana-step.completed {
  opacity: 0.8;
}

.nanobanana-step-icon {
  font-size: 1.1em;
  width: 24px;
  text-align: center;
}

.nanobanana-step-label {
  flex: 1;
}

.nanobanana-estimated-time {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9em;
  margin-bottom: 20px;
}

.nanobanana-button-container {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 15px;
}

.nanobanana-cancel-button,
.nanobanana-close-button {
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
}

/* ==================== Error State ==================== */
.nanobanana-error-state {
  text-align: center;
}

.nanobanana-error-title {
  color: var(--text-error);
  margin-bottom: 20px;
}

.nanobanana-error-box {
  background: rgba(var(--color-red-rgb), 0.1);
  border: 1px solid var(--text-error);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
  text-align: left;
}

.nanobanana-error-details {
  font-size: 0.85em;
  color: var(--text-muted);
  margin-top: 8px;
}

.nanobanana-suggestions {
  background: var(--background-secondary);
  border-radius: 8px;
  padding: 15px;
  text-align: left;
  margin-bottom: 15px;
}

.nanobanana-suggestions p {
  font-weight: bold;
  margin-bottom: 8px;
}

.nanobanana-suggestions ul {
  margin: 0;
  padding-left: 20px;
}

.nanobanana-suggestions li {
  margin: 4px 0;
  color: var(--text-muted);
}

.nanobanana-retry-button {
  margin-right: 10px;
}

/* ==================== Success State ==================== */
.nanobanana-success-state {
  text-align: center;
}

.nanobanana-success-title {
  color: var(--text-success);
  margin-bottom: 20px;
}

.nanobanana-success-box {
  background: rgba(var(--color-green-rgb), 0.1);
  border: 1px solid var(--text-success);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
}

/* ==================== Preview Modal ==================== */
.nanobanana-preview-modal {
  padding: 20px;
  min-width: 500px;
  max-width: 700px;
}

.nanobanana-preview-title {
  text-align: center;
  margin-bottom: 20px;
}

.nanobanana-preview-info {
  background: var(--background-secondary);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 15px;
}

.nanobanana-preview-info-item {
  padding: 4px 0;
  font-size: 0.9em;
}

.nanobanana-textarea-container {
  margin-bottom: 15px;
}

.nanobanana-textarea-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.nanobanana-prompt-textarea {
  width: 100%;
  min-height: 200px;
  padding: 12px;
  border: 1px solid var(--background-modifier-border);
  border-radius: 8px;
  font-family: var(--font-monospace);
  font-size: 0.9em;
  resize: vertical;
  background: var(--background-primary);
  color: var(--text-normal);
}

.nanobanana-prompt-textarea:focus {
  border-color: var(--interactive-accent);
  outline: none;
}

.nanobanana-char-count {
  text-align: right;
  font-size: 0.8em;
  color: var(--text-muted);
  margin-top: 4px;
}

.nanobanana-tips {
  background: var(--background-secondary);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 15px;
  font-size: 0.9em;
}

.nanobanana-tips p {
  margin: 0 0 8px 0;
  font-weight: 500;
}

.nanobanana-tips ul {
  margin: 0;
  padding-left: 20px;
}

.nanobanana-tips li {
  color: var(--text-muted);
  margin: 4px 0;
}

/* ==================== Quick Options Modal ==================== */
.nanobanana-quick-options {
  padding: 20px;
}

.nanobanana-modal-title {
  margin: 0 0 8px 0;
  font-size: 1.4em;
}

.nanobanana-modal-desc {
  color: var(--text-muted);
  margin-bottom: 20px;
}

.nanobanana-btn {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  border: none;
  transition: all 0.2s ease;
}

.nanobanana-btn-cancel {
  background: var(--background-modifier-border);
  color: var(--text-normal);
}

.nanobanana-btn-cancel:hover {
  background: var(--background-modifier-hover);
}

.nanobanana-btn-primary {
  background: var(--interactive-accent);
  color: var(--text-on-accent);
}

.nanobanana-btn-primary:hover {
  background: var(--interactive-accent-hover);
}

.nanobanana-cartoon-settings {
  padding: 10px;
  margin: 10px 0;
  border-radius: 8px;
  background: var(--background-secondary);
  border: 1px solid var(--background-modifier-border);
}

.nanobanana-cartoon-settings .setting-item {
  padding: 8px 0;
  border-bottom: none;
}

/* ==================== Utility Classes ==================== */
.nanobanana-hidden {
  display: none !important;
}

/* ==================== Settings Tab ==================== */
.nanobanana-about {
  background: var(--background-secondary);
  border-radius: 8px;
  padding: 15px;
  text-align: center;
}

.nanobanana-about p {
  margin: 5px 0;
}

.nanobanana-links {
  margin-top: 10px;
}

.nanobanana-links a {
  color: var(--interactive-accent);
  text-decoration: none;
}

.nanobanana-links a:hover {
  text-decoration: underline;
}

/* ==================== Animations ==================== */
@keyframes nanobanana-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.nanobanana-step.active .nanobanana-step-icon {
  animation: nanobanana-spin 1s linear infinite;
}

/* ==================== Dark Theme Adjustments ==================== */
.theme-dark .nanobanana-error-box {
  background: rgba(255, 100, 100, 0.1);
}

.theme-dark .nanobanana-success-box {
  background: rgba(100, 255, 100, 0.1);
}

/* ==================== Mobile Responsive ==================== */
@media (max-width: 600px) {
  .nanobanana-progress-modal,
  .nanobanana-preview-modal {
    min-width: unset;
    width: 100%;
    padding: 15px;
  }

  .nanobanana-button-container {
    flex-direction: column;
  }

  .nanobanana-button-container button {
    width: 100%;
  }
}
```
