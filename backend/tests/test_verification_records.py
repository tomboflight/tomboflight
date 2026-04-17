import unittest
from unittest.mock import patch

from bson import ObjectId

from app.routes import verification_records as verification_routes
from app.schemas.verification_record import (
    VerificationRecordCreate,
    build_verification_record_response,
)
from app.services import verification_record_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class FakeCursor(list):
    def sort(self, field_name, direction):
        return FakeCursor(
            sorted(
                self,
                key=lambda item: str(item.get(field_name) or ""),
                reverse=direction < 0,
            )
        )

    def limit(self, limit):
        return FakeCursor(self[:limit])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def insert_one(self, document):
        stored = dict(document)
        inserted_id = stored.get("_id") or ObjectId()
        stored["_id"] = inserted_id
        self.documents.append(stored)
        return FakeInsertResult(inserted_id)

    def find_one(self, query):
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def find(self, query=None):
        query = query or {}
        return FakeCursor(
            [document for document in self.documents if self._matches(document, query)]
        )

    def update_one(self, query, update):
        document = self.find_one(query)
        if not document:
            return FakeUpdateResult(0)

        set_values = update.get("$set", {})
        document.update(set_values)
        return FakeUpdateResult(1)

    def _matches(self, document, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(document, option) for option in expected):
                    return False
                continue

            actual = document.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    values = expected["$in"]
                    if isinstance(actual, list):
                        if not any(item in values for item in actual):
                            return False
                    elif actual not in values:
                        return False
                elif "$exists" in expected:
                    exists = key in document
                    if bool(expected["$exists"]) != exists:
                        return False
                else:
                    return False
            elif actual != expected:
                return False

        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

    def __getattr__(self, name):
        return self[name]


class VerificationRecordSchemaTests(unittest.TestCase):
    def test_legacy_record_response_normalizes_without_crashing(self):
        response = build_verification_record_response(
            {
                "_id": ObjectId(),
                "relationship_id": "relationship-1",
                "canonical_person_id": "person-1",
                "record_type": "birth_certificate",
                "document_url": "/legacy/birth.pdf",
                "verification_status": "approved",
                "verified_by": "legacy-admin@example.com",
                "notes": "Legacy note",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )

        self.assertEqual(response.verification_type, "birth_certificate")
        self.assertEqual(response.record_type, "birth_certificate")
        self.assertEqual(response.document_url, "/legacy/birth.pdf")
        self.assertEqual(response.verification_status, "verified")
        self.assertEqual(response.status, "verified")
        self.assertEqual(response.reviewed_by, "legacy-admin@example.com")
        self.assertEqual(response.review_notes, "Legacy note")
        self.assertIn("/legacy/birth.pdf", response.evidence_files)

    def test_document_url_falls_back_to_first_evidence_file(self):
        response = build_verification_record_response(
            {
                "_id": ObjectId(),
                "verification_type": "obituary",
                "verification_status": "pending",
                "evidence_files": ["/evidence/obituary.pdf"],
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )

        self.assertEqual(response.document_url, "/evidence/obituary.pdf")
        self.assertEqual(response.record_type, "obituary")


class VerificationRecordServiceTests(unittest.TestCase):
    def test_create_and_list_records_use_canonical_fields(self):
        db = FakeDatabase({"verification_records": []})
        payload = VerificationRecordCreate(
            family_id="family-1",
            member_id="member-1",
            record_type="marriage_certificate",
            document_url="/legacy/marriage.pdf",
            verification_status="pending",
            verified_by="reviewer@example.com",
            notes="Created from legacy payload",
        )

        with patch.object(verification_record_service, "get_database", return_value=db):
            created = verification_record_service.create_verification_record(payload)
            listed = verification_record_service.list_verification_records()

        self.assertEqual(created["verification_type"], "marriage_certificate")
        self.assertEqual(created["verification_status"], "pending")
        self.assertEqual(created["reviewed_by"], "reviewer@example.com")
        self.assertEqual(created["review_notes"], "Created from legacy payload")
        self.assertEqual(created["record_type"], "marriage_certificate")
        self.assertEqual(created["document_url"], "/legacy/marriage.pdf")
        self.assertEqual(len(listed), 1)


class MemberVerificationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.member_id = ObjectId()
        self.evidence_upload_id = ObjectId()
        self.db = FakeDatabase(
            {
                "family_members": [
                    {
                        "_id": self.member_id,
                        "family_id": "family-1",
                        "first_name": "Ada",
                        "last_name": "Byron",
                        "is_verified": False,
                        "verification_status": "unverified",
                    }
                ],
                "verification_records": [],
                "uploaded_files": [
                    {
                        "_id": self.evidence_upload_id,
                        "family_id": "family-1",
                        "member_id": str(self.member_id),
                        "category": "verification_evidence",
                        "verification_type": "birth_certificate",
                        "evidence_kind": "birth_certificate",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
            }
        )
        self.current_user = {
            "id": "reviewer-1",
            "email": "reviewer@example.com",
        }

    def _payload(self):
        return verification_routes.MemberVerificationActionPayload(
            verification_type="birth_certificate",
            verification_method="document_review",
            review_notes="Reviewed source documents.",
            evidence_summary="Birth certificate matched family record.",
            evidence_files=[],
        )

    def _run_with_db(self, callback):
        with patch.object(verification_routes, "get_database", return_value=self.db):
            return callback()

    def test_verify_member_updates_member_and_links_evidence(self):
        response = self._run_with_db(
            lambda: verification_routes.verify_member_route(
                str(self.member_id),
                self._payload(),
                current_user=self.current_user,
            )
        )

        self.assertTrue(response["member"]["is_verified"])
        self.assertEqual(response["member"]["verification_status"], "verified")
        self.assertEqual(response["member"]["verification_method"], "document_review")
        self.assertEqual(response["member"]["verified_by"], "reviewer@example.com")

        record = response["verification_record"]
        self.assertEqual(record.verification_type, "birth_certificate")
        self.assertEqual(record.verification_status, "verified")
        self.assertEqual(record.status, "verified")
        self.assertEqual(record.reviewed_by, "reviewer@example.com")
        self.assertEqual(record.evidence_upload_ids, [str(self.evidence_upload_id)])

    def test_reject_member_updates_member_and_record(self):
        response = self._run_with_db(
            lambda: verification_routes.reject_member_verification_route(
                str(self.member_id),
                self._payload(),
                current_user=self.current_user,
            )
        )

        self.assertFalse(response["member"]["is_verified"])
        self.assertEqual(response["member"]["verification_status"], "rejected")
        self.assertEqual(response["verification_record"].verification_status, "rejected")

    def test_pending_member_updates_member_and_record(self):
        response = self._run_with_db(
            lambda: verification_routes.mark_member_verification_pending_route(
                str(self.member_id),
                self._payload(),
                current_user=self.current_user,
            )
        )

        self.assertFalse(response["member"]["is_verified"])
        self.assertEqual(response["member"]["verification_status"], "pending")
        self.assertEqual(response["verification_record"].verification_status, "pending")

    def test_clear_member_unverifies_member_and_record(self):
        response = self._run_with_db(
            lambda: verification_routes.clear_member_verification_route(
                str(self.member_id),
                verification_routes.MemberVerificationClearPayload(
                    review_notes="Reset after mistaken approval."
                ),
                current_user=self.current_user,
            )
        )

        self.assertFalse(response["member"]["is_verified"])
        self.assertEqual(response["member"]["verification_status"], "unverified")
        self.assertEqual(response["member"]["verification_method"], "")
        self.assertEqual(response["verification_record"].verification_type, "clear_verification")
        self.assertEqual(response["verification_record"].verification_status, "unverified")

    def test_list_member_records_reads_new_records(self):
        self._run_with_db(
            lambda: verification_routes.verify_member_route(
                str(self.member_id),
                self._payload(),
                current_user=self.current_user,
            )
        )

        records = self._run_with_db(
            lambda: verification_routes.get_verification_records_for_member(
                str(self.member_id),
                current_user=self.current_user,
            )
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].verification_status, "verified")
        self.assertEqual(records[0].record_type, "birth_certificate")


if __name__ == "__main__":
    unittest.main()
