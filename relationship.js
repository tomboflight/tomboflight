<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Create Relationship | Tomb of Light</title>
  <meta
    name="description"
    content="Create a relationship between family members in Tomb of Light."
  />
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="page-wrap">
    <header class="site-header">
      <div class="container site-header-inner">
        <a class="brand" href="index.html" aria-label="Tomb of Light home">
          <span>Tomb of Light<span class="brand-symbol">™</span></span>
        </a>

        <nav class="site-nav" id="site-nav" aria-label="Primary navigation">
          <a href="platform.html">Platform</a>
          <a href="how-it-works.html">How It Works</a>
          <a href="security.html">Security</a>
          <a href="faq.html">FAQ</a>
        </nav>

        <div class="header-actions">
          <a class="btn btn-secondary" href="dashboard.html">Dashboard</a>
          <button class="btn btn-secondary" type="button" data-logout-btn>Log Out</button>
        </div>
      </div>
    </header>

    <main data-dashboard>
      <section class="page-hero">
        <div class="container">
          <div class="page-hero-panel">
            <span class="eyebrow">Relationship Mapping</span>
            <h1>Create a Family Relationship</h1>
            <p>
              Connect family members through parent-child, spouse, sibling, guardian, adoptive, or step-family relationships.
            </p>
          </div>
        </div>
      </section>

      <section class="page-sections">
        <div class="container form-shell" data-auth-required style="display: none;">
          <div class="form-panel">
            <form class="form-grid" data-relationship-form novalidate>
              <label>
                Family
                <select name="family_id" required>
                  <option value="">Select a family</option>
                </select>
              </label>

              <div class="form-grid two-col">
                <label>
                  Source Member
                  <select name="source_member_id" required>
                    <option value="">Select a member</option>
                  </select>
                </label>

                <label>
                  Target Member
                  <select name="target_member_id" required>
                    <option value="">Select a member</option>
                  </select>
                </label>
              </div>

              <label>
                Relationship Type
                <select name="relationship_type" required>
                  <option value="">Select relationship type</option>
                  <option value="parent_child">Parent / Child</option>
                  <option value="spouse">Spouse</option>
                  <option value="sibling">Sibling</option>
                  <option value="guardian">Guardian</option>
                  <option value="adoptive_parent_child">Adoptive Parent / Child</option>
                  <option value="step_parent_child">Step Parent / Child</option>
                </select>
              </label>

              <label>
                Created By
                <input
                  type="text"
                  name="created_by"
                  placeholder="Your name or email"
                />
              </label>

              <label>
                Notes
                <textarea
                  name="notes"
                  rows="5"
                  placeholder="Optional notes about this relationship."
                ></textarea>
              </label>

              <div
                class="helper"
                data-relationship-status
                aria-live="polite"
                style="display: none;"
              ></div>

              <div class="inline-actions">
                <button class="btn btn-primary" type="submit" data-submit-btn>
                  Create Relationship
                </button>
                <a class="btn btn-secondary" href="dashboard.html">Back to Dashboard</a>
              </div>
            </form>
          </div>

          <div class="form-panel">
            <span class="eyebrow">Supported Relationship Types</span>

            <div class="grid-3">
              <div>
                <div class="card-number">1</div>
                <h3>Verified family structure</h3>
                <p class="card-copy">
                  Parent-child and spouse relationships form the verified lineage backbone.
                </p>
              </div>

              <div>
                <div class="card-number">2</div>
                <h3>Narrative family structure</h3>
                <p class="card-copy">
                  Guardian, adoptive, and step-family relationships support lived family realities.
                </p>
              </div>

              <div>
                <div class="card-number">3</div>
                <h3>Future tree generation</h3>
                <p class="card-copy">
                  These relationship records prepare Tomb of Light for graph generation and lineage views.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="container">
        <div class="footer-card">
          <div class="footer-bottom">
            <span>© 2026 Tomb of Light LLC. All rights reserved.</span>
          </div>
        </div>
      </div>
    </footer>
  </div>

  <script src="config.js"></script>
  <script src="app.js"></script>
  <script src="auth.js"></script>
  <script src="relationship.js"></script>
</body>
</html>