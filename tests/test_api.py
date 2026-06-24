def _image_upload(name="id.jpg"):
    return {"file": (name, b"fake-image-bytes", "image/jpeg")}


def test_submit_returns_job_id_and_job_completes_with_a_verdict(client):
    resp = client.post("/documents", files=_image_upload())
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert job_id

    job = client.get(f"/jobs/{job_id}")
    assert job.status_code == 200
    body = job.json()
    assert body["status"] == "done"
    # A single-image upload yields exactly one result (no false splits).
    assert len(body["results"]) == 1
    assert body["results"][0]["validation_status"] in {"accepted", "incomplete", "invalid_type"}


def _run(client):
    """Run a single-image upload through the seam and return its sole result."""
    job_id = client.post("/documents", files=_image_upload()).json()["job_id"]
    results = client.get(f"/jobs/{job_id}").json()["results"]
    assert len(results) == 1
    return results[0]


def test_accepted_document_reports_accepted_with_extracted_data(make_client, accepted_fake):
    result = _run(make_client(accepted_fake))
    assert result["validation_status"] == "accepted"
    assert {f["name"] for f in result["extracted_data"]} == {"nachname", "seriennummer"}
    assert result["deficiencies"] == []


def test_incomplete_document_lists_missing_field_as_deficiency(make_client, incomplete_fake):
    result = _run(make_client(incomplete_fake))
    assert result["validation_status"] == "incomplete"
    assert [d["field"] for d in result["deficiencies"]] == ["seriennummer"]


def test_wrong_type_reports_invalid_type_and_skips_extraction(make_client, wrong_type_fake):
    result = _run(make_client(wrong_type_fake))
    assert result["validation_status"] == "invalid_type"
    assert result["extracted_data"] == []


def test_unknown_job_returns_404(client):
    resp = client.get("/jobs/does-not-exist")
    assert resp.status_code == 404


def test_openapi_schema_is_reachable(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/documents" in resp.json()["paths"]
