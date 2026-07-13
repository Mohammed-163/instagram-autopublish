"""
Validation test: uploads a tiny real video to Google Drive, makes it public,
then attempts to publish it as a real Instagram Reel via the Graph API.

This is THE critical early test — it validates that a Drive public link
is fetchable by Instagram's servers before any further system is built.

Run manually only (not scheduled). Posts a REAL reel to your account —
delete it manually from Instagram afterwards if you don't want it to stay up.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.drive_client import DriveClient
from lib.instagram_client import InstagramClient, InstagramAPIError

REQUIRED_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_DRIVE_FOLDER_ID",
    "IG_ACCESS_TOKEN",
    "IG_BUSINESS_ID",
]


def make_test_video(output_path: str) -> str:
    """Generates a trivial 6-second solid-color test video with silent audio,
    entirely locally via ffmpeg — no external image needed for this test."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=navy:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:d={config.VIDEO_DURATION_SECONDS}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return output_path


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    service_account_json = config.require_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    drive_folder_id = config.require_env("GOOGLE_DRIVE_FOLDER_ID")
    ig_token = config.require_env("IG_ACCESS_TOKEN")
    ig_business_id = config.require_env("IG_BUSINESS_ID")

    print("1/6 — Generating a small local test video...")
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "test_reel.mp4")
        make_test_video(video_path)
        print(f"    ✓ Created {video_path} ({os.path.getsize(video_path)} bytes)")

        print("2/6 — Connecting to Google Drive...")
        drive = DriveClient(service_account_json, drive_folder_id)

        print("3/6 — Uploading test video to Drive...")
        file_id = drive.upload_video(video_path, "system_test_reel.mp4", drive_folder_id)
        print(f"    ✓ Uploaded, file_id={file_id}")

        print("4/6 — Making the file publicly accessible...")
        drive.make_public(file_id)
        public_url = drive.get_public_download_url(file_id)
        print(f"    ✓ Public URL: {public_url}")

        print("5/6 — Verifying Instagram token...")
        ig = InstagramClient(ig_token, ig_business_id)
        if not ig.verify_token():
            print("❌ Token verification failed. Check IG_ACCESS_TOKEN / IG_BUSINESS_ID.")
            sys.exit(1)
        print("    ✓ Token is valid")

        print("6/6 — Publishing test Reel via Instagram Graph API...")
        try:
            media_id = ig.publish_reel(
                video_url=public_url,
                caption="🧪 منشور اختباري تلقائي للتحقق من عمل النظام — يمكن حذفه.",
            )
            print(f"    ✅ SUCCESS — published media_id={media_id}")
            print("\n🎉 Validation test PASSED. The Drive → Instagram pipeline works end to end.")
            print("You may now delete the test Reel manually from your Instagram account.")
        except InstagramAPIError as e:
            print(f"    ❌ FAILED to publish: {e}")
            print("\nThis likely means Instagram could not fetch the Drive video_url directly.")
            print("Consider an alternative host for video_url if this persists.")
            sys.exit(1)

        print("\nCleaning up test file from Drive...")
        drive.delete_file(file_id)
        print("✓ Test file removed from Drive.")


if __name__ == "__main__":
    main()
