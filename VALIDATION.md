## Mục tiêu của bộ kiểm tra

Hệ thống đánh giá một phiên dữ liệu dựa trên hai thành phần:

- File CSV: chứa dữ liệu frame, timestamp, camera, FOV, input
- File MP4: chứa video ghi hình thực tế

Mục tiêu là phát hiện sớm các vấn đề ảnh hưởng đến chất lượng dữ liệu, tính đồng bộ giữa CSV và video, cũng như khả năng sử dụng dữ liệu cho các bước xử lý phía sau.

## Nguyên tắc đánh giá kết quả

Mỗi nhóm kiểm tra sẽ trả về một trong ba mức:

- `PASS`: đạt yêu cầu
- `WARN`: có dấu hiệu bất thường nhưng chưa đến mức hỏng dữ liệu
- `FAIL`: không đạt yêu cầu

Lưu ý quan trọng:

- Trong logic hiện tại, nếu chỉ có `WARN` mà không có `FAIL`, trạng thái tổng cuối cùng vẫn được quy đổi thành `PASS`
- Nói cách khác, `WARN` hiện được xem là cảnh báo nội bộ, không làm phiên bị đánh trượt ở kết quả cuối

## Các ngưỡng kiểm tra hiện tại

Hệ thống đang sử dụng các ngưỡng sau:

- Độ phân giải video tối thiểu: `1920 x 1080`
- Chênh lệch đồng bộ cảnh báo: `500 ms`
- Chênh lệch đồng bộ không đạt: `1000 ms`
- Khoảng cách frame bắt đầu được xem là bất thường: `> 34 ms`
- Khoảng cách frame lỗi nghiêm trọng: `> 60 ms`
- Thời lượng phiên tối thiểu: `3000 ms`
- Số dòng CSV tối thiểu để tránh cảnh báo dữ liệu quá ít: `10`
- Sai số chấp nhận cho dòng cuối của ma trận camera: `1e-3`
- Giá trị FOV hợp lệ: từ `1.0` đến `179.0`
- Giá trị `FOV_Axis` hợp lệ: `horizontal`, `vertical`

## 1. Kiểm tra cấu trúc CSV

### Mục đích

Đảm bảo file CSV có đủ cấu trúc tối thiểu để các bước kiểm tra tiếp theo có thể chạy chính xác.

### Các cột bắt buộc

CSV phải có đầy đủ các cột sau:

- `Frame_ID`
- `Timestamp_ms`
- `FOV_Deg`
- `FOV_Axis`
- `Keyboard_Input`
- `Mouse_Delta_X`
- `Mouse_Delta_Y`
- `C2W_M00` đến `C2W_M33` (16 cột ma trận camera)

### Trường hợp không đạt

CSV sẽ bị đánh `FAIL` nếu xảy ra một trong các trường hợp sau:

- File CSV rỗng
- Thiếu bất kỳ cột bắt buộc nào
- Có giá trị trống trong các cột bắt buộc
- Có dữ liệu không thể chuyển thành số trong các cột số

### Trường hợp cảnh báo

CSV sẽ bị đánh `WARN` nếu:

- Số dòng dữ liệu nhỏ hơn `10`

### Ý nghĩa nghiệp vụ

Nhóm kiểm tra này giúp phát hiện các lỗi dữ liệu đầu vào cơ bản, ví dụ:

- xuất sai schema
- thiếu cột
- cột số bị ghi sai định dạng
- dữ liệu quá ít để đại diện cho một phiên hợp lệ

## 2. Kiểm tra timeline trong CSV

### Mục đích

Đánh giá tính liên tục và hợp lý của chuỗi frame và timestamp trong CSV.

### Nội dung kiểm tra

Hệ thống kiểm tra các điểm sau:

- `Frame_ID` có tăng dần nghiêm ngặt hay không
- `Frame_ID` có đi tuần tự từng bước `+1` hay không
- `Timestamp_ms` có tăng dần hay không
- Có timestamp âm hay không
- Có timestamp trùng nhau hay không
- Thời lượng phiên có đủ dài hay không
- Các khoảng cách giữa hai frame liên tiếp có bất thường hay không

### Trường hợp không đạt

Timeline sẽ bị đánh `FAIL` nếu xảy ra một trong các trường hợp sau:

- `Frame_ID` hoặc `Timestamp_ms` không phải dữ liệu số
- `Frame_ID` không tăng dần
- `Frame_ID` không tuần tự từng bước 1
- Có timestamp âm
- `Timestamp_ms` không tăng dần
- Thời lượng phiên ngắn hơn `3000 ms`
- Có ít nhất 1 khoảng frame lớn hơn `60 ms`
- Hoặc có từ `10` khoảng frame lớn hơn `34 ms` trở lên

### Trường hợp cảnh báo

Timeline sẽ bị đánh `WARN` nếu:

- Có từ `1` đến `9` khoảng frame lớn hơn `34 ms`

### Ý nghĩa nghiệp vụ

Nhóm kiểm tra này phản ánh độ ổn định của dữ liệu ghi theo thời gian. Nếu timeline lỗi, dữ liệu thường không còn đáng tin cậy cho các phân tích đồng bộ hoặc chất lượng chuyển động.

## 3. Kiểm tra ma trận camera

### Mục đích

Xác minh dữ liệu pose/camera trong CSV không bị hỏng hoặc sai định dạng.

### Nội dung kiểm tra

Hệ thống kiểm tra:

- Có giá trị `NaN` trong 16 cột ma trận camera hay không
- Có giá trị `Inf` hay không
- Dòng cuối của ma trận có gần với dạng chuẩn `[0, 0, 0, 1]` hay không

### Trường hợp không đạt

Ma trận camera sẽ bị đánh `FAIL` nếu:

- Có giá trị `NaN`
- Có giá trị `Inf`
- Dòng cuối không gần với `[0, 0, 0, 1]` trong sai số cho phép

### Ý nghĩa nghiệp vụ

Đây là nhóm kiểm tra rất quan trọng với dữ liệu không gian. Nếu ma trận camera sai, các bước dựng lại chuyển động hoặc sử dụng pose về sau có thể bị ảnh hưởng trực tiếp.

## 4. Kiểm tra FOV

### Mục đích

Đảm bảo thông tin trường nhìn của camera hợp lệ và nhất quán.

### Nội dung kiểm tra

Hệ thống kiểm tra:

- `FOV_Deg` có nằm trong khoảng hợp lệ hay không
- `FOV_Axis` có thuộc tập giá trị được chấp nhận hay không

### Trường hợp không đạt

FOV sẽ bị đánh `FAIL` nếu:

- `FOV_Deg` nhỏ hơn `1.0` hoặc lớn hơn `179.0`
- `FOV_Deg` không thể đọc thành số
- `FOV_Axis` không phải `horizontal` hoặc `vertical`

### Ý nghĩa nghiệp vụ

Thông tin FOV sai có thể làm sai các phép tính liên quan đến góc nhìn, phối cảnh và các bước xử lý hình học phía sau.

## 5. Kiểm tra input trong CSV

### Mục đích

Đánh giá dữ liệu input người chơi, bao gồm bàn phím và chuột, có hợp lệ hay không.

### Nội dung kiểm tra

Hệ thống kiểm tra:

- `Mouse_Delta_X` và `Mouse_Delta_Y` có phải dữ liệu số hay không
- Có ghi nhận hoạt động bàn phím hoặc chuột hay không

### Trường hợp không đạt

Nhóm này sẽ bị đánh `FAIL` nếu:

- Dữ liệu delta chuột không phải số

### Lưu ý hiện tại

- Hệ thống có cờ cấu hình `require_activity`
- Ở cấu hình hiện tại, cờ này đang là `false`
- Điều đó có nghĩa là một phiên không có hoạt động input vẫn không bị đánh trượt chỉ vì lý do đó

### Ý nghĩa nghiệp vụ

Nhóm kiểm tra này chủ yếu giúp phát hiện dữ liệu input bị lỗi định dạng. Việc có hay không có activity hiện chưa được dùng làm tiêu chí loại phiên.

## 6. Kiểm tra metadata video

### Mục đích

Đảm bảo file MP4 đọc được và có thông tin cơ bản đạt chuẩn tối thiểu.

### Nội dung kiểm tra

Hệ thống sử dụng `ffprobe` để đọc metadata video và kiểm tra:

- Có stream video hay không
- Độ phân giải video
- FPS của video
- Thời lượng video

### Trường hợp không đạt

Video sẽ bị đánh `FAIL` nếu:

- Không đọc được metadata bằng `ffprobe`
- Không tìm thấy video stream trong file MP4
- Độ phân giải thấp hơn `1920 x 1080`
- Không đọc được thời lượng hoặc thời lượng không hợp lệ

### Lưu ý hiện tại

- FPS của video được đọc để phục vụ bước so sánh đồng bộ FPS
- Ở validator video hiện tại, FPS thấp hoặc cao bất thường chưa tự động làm video `FAIL`

### Ý nghĩa nghiệp vụ

Nhóm kiểm tra này giúp sàng lọc các file video không đủ chất lượng tối thiểu hoặc bị lỗi ở mức file/media.

## 7. Kiểm tra đồng bộ thời lượng giữa CSV và video

### Mục đích

Đo độ khớp giữa thời lượng video và timestamp cuối cùng của CSV.

### Cách tính

Hệ thống tính:

- `delta_ms = |thời lượng video theo mili giây - timestamp cuối cùng của CSV|`

### Trường hợp không đạt

Kiểm tra đồng bộ sẽ bị đánh `FAIL` nếu:

- Video đã lỗi từ bước trước
- Không đọc được thời lượng video
- `Timestamp_ms` của CSV không hợp lệ
- `delta_ms > 1000 ms`

### Trường hợp cảnh báo

Kiểm tra đồng bộ sẽ bị đánh `WARN` nếu:

- `500 ms < delta_ms <= 1000 ms`

### Ý nghĩa nghiệp vụ

Đây là một chỉ số quan trọng để đánh giá CSV và video có thực sự thuộc cùng một phiên hay không, hoặc có bị lệch quá trình capture/encode hay không.

## 8. Kiểm tra đồng bộ FPS giữa CSV và video

### Mục đích

So sánh FPS của video với FPS ước tính từ dữ liệu timestamp trong CSV.

### Cách tính

FPS của CSV được ước tính theo công thức:

- `csv_fps = 1000 / delta_ms_mean`

Trong đó `delta_ms_mean` là khoảng cách trung bình giữa hai timestamp liên tiếp.

### Quy tắc đánh giá

- Nếu FPS video nằm trong khoảng `30` đến `35`, thì FPS từ CSV phải nằm trong khoảng `25` đến `35`
- Nếu FPS video nằm trong khoảng `60` đến `65`, thì FPS từ CSV phải nằm trong khoảng `55` đến `65`
- Với các trường hợp khác, FPS từ CSV phải nằm trong khoảng `80%` đến `120%` FPS video

### Trường hợp không đạt

Kiểm tra này sẽ bị đánh `FAIL` nếu:

- Thiếu FPS video
- Thiếu dữ liệu timeline để tính FPS từ CSV
- Khoảng timestamp trung bình không hợp lệ
- FPS từ CSV nằm ngoài khoảng cho phép

### Ý nghĩa nghiệp vụ

Nhóm kiểm tra này giúp phát hiện các trường hợp video và CSV không khớp về tần suất ghi dữ liệu, từ đó ảnh hưởng đến tính nhất quán khi phân tích chuyển động hoặc đồng bộ hình ảnh.

## 9. Cách hiểu kết quả tổng

Kết quả tổng được lấy theo mức nghiêm trọng cao nhất trong tất cả các nhóm kiểm tra:

- `PASS < WARN < FAIL`

Tuy nhiên, do cấu hình hiện tại:

- Nếu kết quả cao nhất là `WARN`, hệ thống vẫn trả ra `PASS`
- Chỉ khi có ít nhất một nhóm `FAIL` thì kết quả tổng mới là `FAIL`

Vì vậy, khi đọc kết quả:

- `PASS` có thể là đạt hoàn toàn
- `PASS` cũng có thể là đạt nhưng có cảnh báo nội bộ
- `FAIL` là không đạt thực sự

## 10. Gợi ý sử dụng tài liệu này

Tài liệu này phù hợp để:

- giải thích cho PM các tiêu chí hệ thống đang dùng
- thống nhất với QA về định nghĩa đạt và không đạt
- trao đổi với team data hoặc team vận hành khi cần đối chiếu nguyên nhân lỗi

Nếu cần, có thể tách tiếp thành 2 bản:

- một bản rất ngắn theo hướng nghiệp vụ để gửi PM
- một bản chi tiết hơn cho QA hoặc kỹ thuật, có ví dụ lỗi thực tế
