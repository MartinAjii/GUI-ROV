import cv2
import sys

def main():
    udp_url = "udp://0.0.0.0:5600"
    print(f"Attempting to open video stream at {udp_url} ...")
    
    # We use CAP_FFMPEG backend explicitly for UDP streams
    cap = cv2.VideoCapture(udp_url, cv2.CAP_FFMPEG)
    
    if not cap.isOpened():
        print("Error: Could not open the UDP stream. Make sure the Pi is sending data to this PC's IP on port 5600.")
        sys.exit(1)
        
    print("Stream opened successfully! Displaying frames (press 'q' to quit).")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Warning: Stopped receiving frames or end of stream.")
            break
            
        cv2.imshow("GCS UDP Stream Test", frame)
        
        # Press 'q' to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
