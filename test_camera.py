"""Quick test to check if camera is accessible."""
import cv2

print("Testing camera access...")

# Try DirectShow (best for Windows)
for idx in (0, 1):
    for backend_name, backend in [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("DEFAULT", cv2.CAP_ANY)]:
        cap = cv2.VideoCapture(idx, backend)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                print(f"✅ Camera {idx} + {backend_name}: WORKS! Resolution: {w}x{h}")
                # Show the camera feed for 5 seconds
                print("Showing camera feed for 5 seconds... Press 'q' to quit early.")
                import time
                start = time.time()
                while time.time() - start < 5:
                    ret, frame = cap.read()
                    if ret:
                        cv2.imshow("Camera Test", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cv2.destroyAllWindows()
                cap.release()
                print("Camera test complete!")
                exit(0)
            else:
                print(f"❌ Camera {idx} + {backend_name}: opened but can't read frames")
                cap.release()
        else:
            print(f"❌ Camera {idx} + {backend_name}: failed to open")
            cap.release()

print("\n⚠️  No working camera found!")
print("Try these fixes:")
print("  1. Windows Settings → Privacy → Camera → Allow apps to access camera")
print("  2. Close any other apps using the camera (Zoom, Teams, etc.)")
print("  3. Check Device Manager → Cameras → make sure it's enabled")
