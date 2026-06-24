# Disposal Video Feature - Quick Start Guide

## For Collectors

### How to Upload a Disposal Video

1. **Login to Collector Dashboard**
   - Navigate to `/collector/login`
   - Use credentials: `rajesh@bmw.com` / `collector123`

2. **Accept a Waste Collection Job**
   - Wait for pickup requests or request one manually
   - Accept the job to get an active trip

3. **Upload Disposal Evidence**
   - Once you have an active job, scroll down to "Upload Disposal Video & Photos" section
   - Click on video file selector to choose your disposal video
   - (Optional) Select geotag photos to attach
   - Click "Get Current Location" to capture GPS coordinates
   - (Optional) Enter disposal site address
   - Click "Upload Video & Photos" button
   - Monitor the upload progress

4. **Success**
   - Video will be automatically sent to the assigned hospital
   - Confirmation message will display

## For Hospitals

### How to View and Review Disposal Videos

1. **Login to Hospital Dashboard**
   - Navigate to `/hospital/login`
   - Use credentials: `apollo@hospital.com` / `hospital123`

2. **Find Disposal Videos Section**
   - Scroll down on the hospital dashboard
   - Look for "♻️ Disposal Evidence Videos" card

3. **View Disposal Video**
   - Click on any video card to open the viewer
   - Video player shows full disposal recording
   - See geotag photos and location data
   - View collector details and upload timestamp

4. **Review and Approve**
   - Click "Review Video" button in modal
   - Select approval status (Approve/Reject)
   - Add optional review notes
   - Submit review
   - Status will update in the video gallery

## Technical Notes

### Video Upload Limits
- **Max File Size**: 500 MB
- **Supported Formats**: MP4, AVI, MOV, MKV, WebM, FLV
- **Max Photos**: Unlimited
- **Max Photo Size**: 50 MB each
- **Supported Photo Formats**: JPG, JPEG, PNG, GIF, WebP

### Location Requirements
- Browser must allow geolocation permission
- HTTPS recommended for production (geolocation requires secure context)
- Location coordinates stored with 6 decimal places precision (~0.1 meters)

### File Storage
- Videos stored in: `/uploads/disposal_media/collector_{id}/`
- Photos stored in: `/uploads/disposal_media/collector_{id}/disposal_{timestamp}_photos/`
- This directory is in `.gitignore` to prevent committing large files

## Troubleshooting

### "No video selected" Error
- Make sure you've selected a video file before uploading

### "Please capture location first" Error
- Click the "Get Current Location" button
- Grant browser permission if prompted
- Wait for location to be captured

### Upload Fails
- Check file format (must be MP4, AVI, MOV, MKV, WebM, or FLV)
- Verify file size is under 500 MB
- Check internet connection
- Try a smaller file

### Geolocation Not Working
- Check browser compatibility (works on Chrome, Firefox, Safari, Edge)
- Ensure page is served over HTTPS (required by browsers)
- Grant permission when browser asks for location access
- Disable VPN if it blocks location services

### No Videos Showing in Hospital Dashboard
- Ensure you're logged in as a hospital
- Videos only appear after collectors upload them
- Refresh the page (auto-refresh every 10 seconds)
- Check if collectors have completed any pickups

## API Endpoints

### Collector API
- `POST /api/disposal/upload` - Upload video and photos

### Hospital API
- `GET /api/disposal/videos` - List all videos for hospital
- `GET /api/disposal/video/{id}` - Get video details
- `POST /api/disposal/video/{id}/review` - Review/approve video
- `GET /upload/disposal/{id}/video` - Download video file
- `GET /upload/disposal/{id}/photo/{photo_name}` - Download photo file

## Database Schema

### disposal_videos Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| collector_id | INTEGER | Collector who uploaded |
| hospital_id | INTEGER | Target hospital |
| request_id | INTEGER | Collection request ID |
| video_filename | TEXT | Stored filename |
| photos_json | TEXT | JSON array of photo paths |
| latitude | REAL | GPS latitude |
| longitude | REAL | GPS longitude |
| address | TEXT | Disposal site address |
| video_duration_sec | INTEGER | Video length in seconds |
| file_size_mb | REAL | File size in MB |
| status | TEXT | pending/approved/rejected |
| notes | TEXT | Collector notes |
| hospital_notes | TEXT | Hospital review notes |
| uploaded_at | TEXT | Upload timestamp |
| reviewed_at | TEXT | Review timestamp |
| reviewed_by_hospital | INTEGER | Flag if hospital reviewed |

## Sample cURL Commands

### Upload Video
```bash
curl -X POST http://localhost:5001/api/disposal/upload \
  -F "video=@disposal.mp4" \
  -F "photos[]=@photo1.jpg" \
  -F "photos[]=@photo2.jpg" \
  -F "latitude=28.6139" \
  -F "longitude=77.2090" \
  -F "address=Test Disposal Site" \
  -F "hospital_id=1" \
  -F "request_id=1"
```

### Get Hospital Videos
```bash
curl -X GET http://localhost:5001/api/disposal/videos \
  -H "Cookie: session=YOUR_SESSION_COOKIE"
```

### Review Video
```bash
curl -X POST http://localhost:5001/api/disposal/video/1/review \
  -H "Content-Type: application/json" \
  -d '{"status":"approved","notes":"Good disposal practices"}'
```
