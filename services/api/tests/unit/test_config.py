from app.core.config import Settings


def test_custom_cors_origins_also_allow_both_public_app_domains():
    settings = Settings(
        database_url="postgresql://example",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-key",
        cors_origins="https://staging.triplyy.net",
    )

    assert settings.cors_origins == [
        "https://staging.triplyy.net",
        "https://triplyy.net",
        "https://www.triplyy.net",
    ]
