import json
import uuid
import random
import os
from datetime import datetime, timezone, timedelta

OUTPUT_PATH = "outputs/week1/intent_records.jsonl"
TARGET_COUNT = 20

# realistic intents for a TypeScript/React codebase
INTENTS = [
    ("Create User API", ["auth", "pii"], [
        ("src/auth/userController.ts", 1, 48, "createUser", 0.92),
        ("src/middleware/validateRequest.ts", 12, 35, "validateRequest", 0.88),
        ("src/auth/passwordHash.ts", 1, 22, "hashPassword", 0.95),
    ]),
    ("Implement Login Flow", ["auth", "security"], [
        ("src/auth/loginController.ts", 1, 50, "loginUser", 0.85),
        ("src/middleware/authMiddleware.ts", 5, 30, "authenticateToken", 0.79),
    ]),
    ("Refactor UI Components", ["ui"], [
        ("webview-ui/src/components/Button.tsx", 1, 40, "Button", 0.88),
        ("webview-ui/src/components/Modal.tsx", 8, 62, "DialogHeader", 0.79),
        ("webview-ui/src/components/Sidebar.tsx", 1, 88, "Sidebar", 0.83),
    ]),
    ("Add Password Reset Flow", ["auth", "pii", "security"], [
        ("src/auth/resetController.ts", 1, 45, "requestReset", 0.90),
        ("src/auth/tokenService.ts", 10, 35, "generateResetToken", 0.87),
        ("src/templates/resetEmail.ts", 1, 25, "buildResetEmail", 0.75),
    ]),
    ("Implement Role-Based Access Control", ["auth", "security", "billing"], [
        ("src/middleware/rbacMiddleware.ts", 1, 60, "checkPermission", 0.93),
        ("src/models/Role.ts", 1, 40, "RoleModel", 0.88),
        ("src/config/permissions.ts", 1, 50, "PERMISSIONS", 0.82),
    ]),
    ("Add Payment Integration", ["billing", "pii"], [
        ("src/payments/stripeService.ts", 1, 80, "processPayment", 0.91),
        ("src/payments/webhookHandler.ts", 5, 45, "handleWebhook", 0.86),
        ("src/models/Transaction.ts", 1, 35, "TransactionModel", 0.78),
    ]),
    ("Create Dashboard Analytics", ["ui"], [
        ("webview-ui/src/components/Dashboard.tsx", 1, 120, "Dashboard", 0.84),
        ("webview-ui/src/hooks/useAnalytics.ts", 1, 45, "useAnalytics", 0.76),
        ("src/analytics/metricsService.ts", 1, 65, "getMetrics", 0.89),
    ]),
    ("Add Email Notification Service", ["pii"], [
        ("src/notifications/emailService.ts", 1, 70, "sendEmail", 0.87),
        ("src/templates/welcomeEmail.ts", 1, 30, "buildWelcomeEmail", 0.81),
        ("src/config/emailConfig.ts", 1, 20, "EMAIL_CONFIG", 0.73),
    ]),
    ("Implement File Upload", ["pii"], [
        ("src/uploads/uploadController.ts", 1, 55, "uploadFile", 0.90),
        ("src/uploads/storageService.ts", 10, 50, "storeFile", 0.85),
        ("src/middleware/fileValidation.ts", 1, 30, "validateFile", 0.88),
    ]),
    ("Add Search Functionality", ["ui"], [
        ("src/search/searchService.ts", 1, 75, "searchDocuments", 0.82),
        ("webview-ui/src/components/SearchBar.tsx", 1, 50, "SearchBar", 0.79),
        ("src/search/indexService.ts", 5, 40, "buildIndex", 0.86),
    ]),
    ("Create API Rate Limiting", ["security"], [
        ("src/middleware/rateLimiter.ts", 1, 40, "rateLimitMiddleware", 0.91),
        ("src/config/rateLimitConfig.ts", 1, 20, "RATE_LIMIT_CONFIG", 0.85),
    ]),
    ("Implement Audit Logging", ["security", "pii"], [
        ("src/audit/auditService.ts", 1, 60, "logAuditEvent", 0.94),
        ("src/models/AuditLog.ts", 1, 35, "AuditLogModel", 0.89),
        ("src/middleware/auditMiddleware.ts", 5, 30, "auditMiddleware", 0.83),
    ]),
    ("Add Two-Factor Authentication", ["auth", "security"], [
        ("src/auth/twoFactorService.ts", 1, 65, "generateTOTP", 0.92),
        ("src/auth/twoFactorController.ts", 1, 50, "verifyTOTP", 0.88),
    ]),
    ("Implement Session Management", ["auth", "security"], [
        ("src/auth/sessionService.ts", 1, 55, "createSession", 0.87),
        ("src/middleware/sessionMiddleware.ts", 5, 35, "validateSession", 0.81),
        ("src/models/Session.ts", 1, 30, "SessionModel", 0.79),
    ]),
    ("Create Data Export Feature", ["pii", "billing"], [
        ("src/export/exportService.ts", 1, 70, "exportUserData", 0.86),
        ("src/export/csvFormatter.ts", 5, 40, "formatCSV", 0.82),
    ]),
    ("Add Webhook Support", ["security"], [
        ("src/webhooks/webhookService.ts", 1, 60, "registerWebhook", 0.89),
        ("src/webhooks/signatureVerifier.ts", 5, 30, "verifySignature", 0.93),
    ]),
    ("Implement Caching Layer", ["ui"], [
        ("src/cache/cacheService.ts", 1, 50, "cacheResponse", 0.85),
        ("src/middleware/cacheMiddleware.ts", 5, 25, "cacheMiddleware", 0.78),
    ]),
    ("Create Admin Panel", ["auth", "billing", "security"], [
        ("webview-ui/src/components/AdminPanel.tsx", 1, 150, "AdminPanel", 0.91),
        ("src/admin/adminController.ts", 1, 80, "AdminController", 0.87),
        ("src/middleware/adminAuthMiddleware.ts", 5, 30, "requireAdmin", 0.94),
    ]),
    ("Add GraphQL API", ["auth"], [
        ("src/graphql/schema.ts", 1, 100, "buildSchema", 0.83),
        ("src/graphql/resolvers.ts", 1, 120, "resolvers", 0.79),
        ("src/graphql/context.ts", 5, 30, "createContext", 0.86),
    ]),
    ("Implement Dark Mode", ["ui"], [
        ("webview-ui/src/hooks/useTheme.ts", 1, 35, "useTheme", 0.77),
        ("webview-ui/src/components/ThemeToggle.tsx", 1, 25, "ThemeToggle", 0.82),
    ]),
]

def generate_record(intent_tuple, days_ago):
    description, governance_tags, code_refs_data = intent_tuple
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)

    code_refs = []
    for file_path, line_start, line_end, symbol, confidence in code_refs_data:
        # add small variance to confidence
        varied_confidence = round(
            min(0.99, max(0.60, confidence + random.uniform(-0.05, 0.05))),
            2
        )
        code_refs.append({
            "file":       file_path,
            "line_start": line_start,
            "line_end":   line_end,
            "symbol":     symbol,
            "confidence": varied_confidence
        })

    return {
        "intent_id":       str(uuid.uuid4()),
        "description":     description,
        "code_refs":       code_refs,
        "governance_tags": governance_tags,
        "created_at":      created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status":          random.choice(["COMPLETED", "IN_PROGRESS", "COMPLETED"]),
        "is_synthetic":    True
    }


def main():
    # load existing real records
    real_records = []
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        real_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    print(f"Loaded {len(real_records)} real records")

    # fix real records — vary confidence from 1.0 placeholders
    fixed_real = []
    for record in real_records:
        for ref in record.get("code_refs", []):
            if ref.get("confidence") == 1.0:
                ref["confidence"] = round(
                    random.uniform(0.75, 0.96), 2
                )
        fixed_real.append(record)

    # generate synthetic records
    needed    = max(0, TARGET_COUNT - len(fixed_real))
    synthetic = []
    for i, intent_tuple in enumerate(INTENTS[:needed]):
        days_ago = random.randint(1, 60)
        synthetic.append(generate_record(intent_tuple, days_ago))

    all_records = fixed_real + synthetic

    os.makedirs("outputs/week1", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"Written {len(all_records)} records to {OUTPUT_PATH}")
    print(f"  real:      {len(fixed_real)}")
    print(f"  synthetic: {len(synthetic)}")


if __name__ == "__main__":
    main()