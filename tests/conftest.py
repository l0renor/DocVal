import pytest
from fastapi.testclient import TestClient

from docval.app import create_app
from docval.config import Config, DocumentTypeConfig, ExpectedField
from docval.model_client import FakeModelClient
from docval.schemas import (
    Classification,
    Deficiency,
    ExtractionOutcome,
    FieldResult,
    Legibility,
    ValidationStatus,
)


@pytest.fixture
def personalausweis_config():
    return Config(
        document_types=[
            DocumentTypeConfig(
                id="personalausweis",
                description="A German national identity card (Personalausweis) or passport.",
                expected_fields=[
                    ExpectedField(name="nachname", description="Surname", type_hint="string"),
                    ExpectedField(name="seriennummer", description="9-character serial number", type_hint="string"),
                ],
                criteria="Must be a valid German ID document; core identification data must be unredacted.",
            )
        ]
    )


def _fake(document_type="personalausweis", extraction=None):
    return FakeModelClient(
        classification=Classification(document_type=document_type),
        extraction=extraction,
    )


@pytest.fixture
def accepted_fake():
    return _fake(
        extraction=ExtractionOutcome(
            validation_status=ValidationStatus.ACCEPTED,
            fields=[
                FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
                FieldResult(name="seriennummer", value="T220001293", legibility=Legibility.LEGIBLE),
            ],
            deficiencies=[],
            internal_note=None,
        )
    )


@pytest.fixture
def incomplete_fake():
    return _fake(
        extraction=ExtractionOutcome(
            validation_status=ValidationStatus.INCOMPLETE,
            fields=[
                FieldResult(name="nachname", value="Mustermann", legibility=Legibility.LEGIBLE),
                FieldResult(name="seriennummer", value=None, legibility=Legibility.ILLEGIBLE),
            ],
            deficiencies=[Deficiency(field="seriennummer", reason="serial number not legible")],
            internal_note=None,
        )
    )


@pytest.fixture
def wrong_type_fake():
    # No canned extraction: if extraction were attempted, FakeModelClient raises,
    # which proves Stufe 2 is skipped on a wrong type.
    return _fake(document_type="katzenfoto", extraction=None)


@pytest.fixture
def make_client(personalausweis_config):
    def _make(model_client):
        return TestClient(create_app(config=personalausweis_config, model_client=model_client))

    return _make


@pytest.fixture
def client(make_client, accepted_fake):
    return make_client(accepted_fake)
