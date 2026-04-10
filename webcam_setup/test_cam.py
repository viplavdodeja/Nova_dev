import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Could not open camera")
    exit()

ret, frame = cap.read()

if not ret:
    print("Camera opened, but no frame was read")
    cap.release()
    exit()

print("Camera works")
print("Frame shape:", frame.shape)

cv2.imwrite("test_frame.jpg", frame)
print("Saved test_frame.jpg")

cap.release()