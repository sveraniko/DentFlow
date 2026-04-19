from app.interfaces.bots.patient.router import _CompactProductPickerItem, _resolve_media_ref


def test_compact_product_row_grammar_supports_recommendation_and_category_contexts() -> None:
    category_row = _CompactProductPickerItem(
        product_id="prod-1",
        title="Nano Brush",
        price_amount=25,
        currency_code="GEL",
        availability="In stock",
        short_label="Soft",
        branch_hint="Main branch",
    )
    recommendation_row = _CompactProductPickerItem(
        product_id="prod-1",
        title="Nano Brush",
        price_amount=25,
        currency_code="GEL",
        availability="In stock",
        short_label="Soft",
        badge="Recommended",
        branch_hint="Main branch",
    )

    assert category_row.button_label() == "Nano Brush · 25 GEL · In stock · Soft · Main branch"
    rec_label = recommendation_row.button_label()
    assert rec_label.startswith("Nano Brush · 25 GEL · In stock · Recommended")
    assert len(rec_label) <= 62


def test_media_ref_resolution_supports_photo_video_and_missing_values() -> None:
    photo = _resolve_media_ref("photo:AgAC-telegram-file-id")
    assert photo is not None
    assert photo.media_kind == "photo"
    assert photo.media_value == "AgAC-telegram-file-id"

    gallery_video = _resolve_media_ref("https://cdn.example.com/care-gallery.mp4")
    assert gallery_video is not None
    assert gallery_video.media_kind == "video"

    fallback_photo = _resolve_media_ref("https://cdn.example.com/care-cover.jpg")
    assert fallback_photo is not None
    assert fallback_photo.media_kind == "photo"

    assert _resolve_media_ref("   ") is None
