# === 0. 라이브러리 임포트 ===
import open3d as o3d
import numpy as np
import cv2  # cv2와 cv는 동일합니다. cv2로 통일합니다.
import matplotlib.pyplot as plt
import random
import sys
from sklearn.linear_model import LinearRegression, RANSACRegressor

# === 1. 뎁스 맵 -> 엣지 맵 생성 함수 (From Script 3) ===

def create_sobel_edge_map(depth_path, output_edge_path, ksize=3):
    """
    [1단계] 원본 뎁스 맵을 읽어 Sobel L2 Norm 엣지 맵을 생성하고 저장합니다.
    """
    print(f"  - 원본 뎁스 맵 로드: {depth_path}")
    try:
        img = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"오류: '{depth_path}' 뎁스 맵을 로드할 수 없습니다.")
            return False
    except Exception as e:
        print(f"오류: 뎁스 맵 로드 중 예외 발생 - {e}")
        return False

    # 8비트로 정규화
    depth_8bit = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # ddepth: 출력 이미지 깊이를 CV_32F로 설정 (정확한 계산을 위해)
    ddepth = cv2.CV_32F

    # X, Y 방향 미분
    grad_x = cv2.Sobel(depth_8bit, ddepth, 1, 0, ksize=ksize)
    grad_y = cv2.Sobel(depth_8bit, ddepth, 0, 1, ksize=ksize)

    grad_x = cv2.convertScaleAbs(grad_x)
    grad_y = cv2.convertScaleAbs(grad_y)

    # 가중치 합산 (L1 노름 근사) - 0.5 가중치는 단순 평균을 의미
    # (0.5 * |grad_x|) + (0.5 * |grad_y|)
    grad_magnitude = cv2.addWeighted(grad_x, 1, grad_y, 1, 0)

    # # L2 노름 (제곱근 합, 표준 방식)
    # # cv2.magnitude() 함수는 sqrt(x^2 + y^2)를 계산합니다.
    # grad_magnitude = cv2.magnitude(grad_x, grad_y)

    # # 8비트 부호 없는 정수(0-255)로 변환하여 .png로 저장
    # grad_magnitude_8bit = cv2.convertScaleAbs(grad_magnitude)

    plt.imshow(grad_magnitude, cmap='gray')
    plt.title(f"Sobel Edge Map (ksize={ksize})")
    plt.show()

    try:
        cv2.imwrite(output_edge_path, grad_magnitude)
        print(f"  - Sobel 엣지 맵 저장 완료: {output_edge_path}")
        return True
    except Exception as e:
        print(f"오류: 엣지 맵 저장 중 예외 발생 - {e}")
        return False


# === 2. 엣지 맵 -> 그루핑 함수 (From Script 2, 파라미터 추가) ===

def group_and_visualize_contours(
    edge_path,
    output_path="contour_groups_visualization.png",
    min_area_threshold=50,
    min_aspect_ratio=3.0,
    threshold=40,
    dilation_ksize=(3, 3)
):
    """
    [2단계] Contours를 사용하여 엣지 맵에서 '영역'을
    찾고 필터링한 뒤, 내부를 채운 그룹 레이블 맵을 생성합니다.
    """
    print(f"  - 엣지 맵 로드: {edge_path}")
    edge_image = cv2.imread(edge_path, cv2.IMREAD_GRAYSCALE)
    if edge_image is None:
        print(f"오류: '{edge_path}' 엣지 이미지를 불러올 수 없습니다.")
        return None, 0

    h, w = edge_image.shape

    # 이진화 (파라미터 사용)
    _, binary_edge = cv2.threshold(edge_image, threshold, 255, cv2.THRESH_BINARY)
    plt.imshow(binary_edge, cmap='gray')
    plt.title(f"Binary Edge Image (Threshold: {threshold})")
    plt.show()

    # Dilation으로 '선'을 '영역'으로 변환 (파라미터 사용)
    kernel = np.ones(dilation_ksize, np.uint8)
    dilated_edge = cv2.dilate(binary_edge, kernel, iterations=1)

    # Contours(윤곽선) 찾기
    contours, hierarchy = cv2.findContours(
        dilated_edge,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        print("  - Contours 결과, 감지된 윤곽선이 없습니다.")
        return np.zeros_like(edge_image, dtype=np.int32), 0

    print(f"  - Contours: 총 {len(contours)}개의 윤곽선(영역) 감지.")

    filtered_labels_map = np.zeros_like(edge_image, dtype=np.int32)
    vis_image = np.zeros((h, w, 3), dtype=np.uint8)
    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)

    group_id = 1
    filtered_count = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area_threshold:
            continue

        rect = cv2.minAreaRect(contour)
        (width, height) = rect[1]

        if width == 0 or height == 0:
            continue

        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio < min_aspect_ratio:
            continue

        # 필터링 통과: 레이블 맵에 그리기
        cv2.drawContours(
            filtered_labels_map,
            [contour],
            contourIdx=-1,
            color=group_id,
            thickness=cv2.FILLED
        )

        # 시각화 맵에 그리기
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        cv2.drawContours(vis_image, [contour], -1, color, thickness=cv2.FILLED)

        # 텍스트 추가
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            ax.text(cx, cy, str(group_id), color='white', fontsize=8,
                    ha='center', va='center', weight='bold',
                    bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=1))

        group_id += 1
        filtered_count += 1

    final_group_count = group_id - 1
    print(f"  - 필터링 후: 총 {final_group_count}개의 유효한 영역(전선) 그룹 감지.")

    # Matplotlib 시각화 저장
    ax.imshow(vis_image)
    ax.set_title(f"Contour Groups (Filtered, Min Area: {min_area_threshold}, Min AR: {min_aspect_ratio})")
    ax.axis('off')
    plt.savefig(output_path, bbox_inches='tight', pad_inches=0)
    print(f"  - '{output_path}'에 Contour 그룹 시각화 이미지 저장 완료.")
    plt.show()
    plt.close(fig)

    return filtered_labels_map, final_group_count


# === 3. 뎁스 회귀 함수 (From Script 2, 파라미터 추가) ===

def calculate_and_replace_depths(
    depth_path,
    labels_map,
    num_groups,
    output_depth_path="regressed_depth_map.tif",
    ransac_threshold=15.0
):
    """
    [3단계] 원본 뎁스 맵과 레이블 맵을 기반으로, RANSAC 회귀를 사용해
    각 그룹의 뎁스 값을 평면으로 교체하고, 새 뎁스 맵을 반환합니다.
    """
    print(f"  - 원본 뎁스 맵 로드: {depth_path}")
    depth_map = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
    if depth_map is None:
        print(f"오류: '{depth_path}' 뎁스 맵을 불러올 수 없습니다.")
        return None

    original_dtype = depth_map.dtype
    print(f"  - 원본 뎁스 맵 로드 완료. Shape: {depth_map.shape}, Dtype: {original_dtype}")

    if depth_map.shape != labels_map.shape:
        print(f"오류: 뎁스 맵({depth_map.shape})과 레이블 맵({labels_map.shape})의 크기가 다릅니다.")
        return None

    # 원본 뎁스 맵을 복사하여 회귀된 뎁스 맵으로 사용
    regressed_depth_map = depth_map.astype(np.float32)

    for i in range(1, num_groups + 1):
        y_coords, x_coords = np.where(labels_map == i)
        num_pixels = len(y_coords)

        # RANSAC 피팅을 위한 최소 픽셀 수 (3개) 확인
        if num_pixels < 3:
            if num_pixels > 0: # 1~2개인 경우 평균값으로 대체
                depth_values = depth_map[y_coords, x_coords]
                representative_depth = np.mean(depth_values)
                regressed_depth_map[y_coords, x_coords] = representative_depth
            continue

        X_data = np.stack((x_coords, y_coords), axis=1)
        y_data = depth_map[y_coords, x_coords].astype(np.float32)

        # RANSAC Regressor 사용 (파라미터 사용)
        ransac = RANSACRegressor(
            estimator=LinearRegression(),
            min_samples=3,
            max_trials=100,
            residual_threshold=ransac_threshold # 튜닝 파라미터
        )

        try:
            ransac.fit(X_data, y_data)
            
            # predicted_depths = ransac.predict(X_data)            
            # # 뎁스 값이 음수가 되는 것 방지
            # predicted_depths[predicted_depths < 0] = 0
            # regressed_depth_map[y_coords, x_coords] = predicted_depths
            # # print(f"   - 그룹 {i} (픽셀 {num_pixels}개) 처리 완료.")

            inlier_mask = ransac.inlier_mask_
            inlier_original_depths = y_data[inlier_mask]            
            representative_depth = np.mean(inlier_original_depths)  # 전선 그룹의 '대표 뎁스'            
            # representative_depth = np.median(inlier_original_depths)  # 또는 노이즈에 더 강건한 중앙값
            regressed_depth_map[y_coords, x_coords] = representative_depth

        except ValueError as e:
            # RANSAC이 실패할 경우 (예: 모든 점이 아웃라이어)
            print(f"   - 경고: 그룹 {i} RANSAC 피팅 실패 ({e}). 원본 값 유지.")
            pass # 원본 값은 이미 regressed_depth_map에 있으므로 스킵

    print(f"  - 총 {num_groups}개 그룹의 뎁스 회귀 처리 완료.")

    # 원본 데이터 타입으로 변환 및 저장
    try:
        if np.issubdtype(original_dtype, np.integer):
            dtype_info = np.iinfo(original_dtype)
            regressed_depth_map = np.clip(regressed_depth_map, dtype_info.min, dtype_info.max)
        
        final_depth_map = regressed_depth_map.astype(original_dtype)
        cv2.imwrite(output_depth_path, final_depth_map)
        print(f"  - '{output_depth_path}'에 회귀가 적용된 새 뎁스 맵 저장 완료.")

        # 시각화를 위해 float32 맵 반환
        return regressed_depth_map.astype(np.float32)

    except Exception as e:
        print(f"오류: 최종 뎁스 맵 저장 중 문제 발생 - {e}")
        return None

# === 4. 포인트 클라우드 생성 함수 (From Script 1, 수정) ===

def create_point_cloud_from_rgbd(
    rgb_path,
    camera_intrinsics,
    depth_path=None,
    depth_image=None, # Numpy 배열을 직접 받을 수 있도록 추가
    depth_scale=1000.0
):
    """
    [4단계] RGB 이미지와 Depth(경로 또는 Numpy 배열)로부터 3D 포인트 클라우드를 생성합니다.
    """
    rgb_image = cv2.imread(rgb_path)
    if rgb_image is None:
        print(f"  - 오류: RGB 이미지를 찾을 수 없습니다: {rgb_path}")
        return None

    # [수정] depth_image(Numpy)가 제공되지 않았다면 depth_path에서 로드
    if depth_image is None:
        if depth_path is None:
            print("  - 오류: 'depth_path' 또는 'depth_image' 중 하나는 제공되어야 합니다.")
            return None
        depth_image = cv2.imread(depth_path, cv2.IMREAD_ANYDEPTH)
        if depth_image is None:
            print(f"  - 오류: Depth 이미지를 찾을 수 없습니다: {depth_path}")
            return None
        print(f"  - (From Path) Depth 정보: {depth_image.shape}, {depth_image.dtype}, min={np.min(depth_image)}, max={np.max(depth_image)}")
    # else:
        # print(f"  - (From Array) Depth 정보: {depth_image.shape}, {depth_image.dtype}, min={np.min(depth_image)}, max={np.max(depth_image)}")


    if rgb_image.shape[:2] != depth_image.shape[:2]:
        print(f"  - 오류: RGB({rgb_image.shape[:2]})와 Depth({depth_image.shape[:2]}) 이미지의 해상도가 다릅니다.")
        return None

    # OpenCV BGR -> RGB
    rgb_image = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2RGB)

    # Open3D의 이미지 객체로 변환
    o3d_rgb = o3d.geometry.Image(rgb_image)
    # [수정] float32가 아닌 경우 o3d.Image가 float32로 변환 시도 (원본 유지)
    if depth_image.dtype != np.float32:
         o3d_depth = o3d.geometry.Image(depth_image.astype(np.float32))
    else:
         o3d_depth = o3d.geometry.Image(depth_image)

    # RGBD 이미지 생성
    rgbd_image = o3d.geometry.RGBDImage.create_from_color_and_depth(
        o3d_rgb,
        o3d_depth,
        depth_scale=(1.0 / depth_scale),
        depth_trunc=1000.0, # 100m -> 1000m (원본 코드가 100이었으나 뎁스 스케일에 따라 조절)
        convert_rgb_to_intensity=False
    )

    # 카메라 파라미터 설정
    width, height = depth_image.shape[1], depth_image.shape[0]
    pinhole_camera_intrinsic = o3d.camera.PinholeCameraIntrinsic(
        width,
        height,
        camera_intrinsics['fx'],
        camera_intrinsics['fy'],
        camera_intrinsics['cx'],
        camera_intrinsics['cy']
    )

    # 포인트 클라우드 생성
    pcd = o3d.geometry.PointCloud.create_from_rgbd_image(
        rgbd_image,
        pinhole_camera_intrinsic
    )

    # 'inf' (무한대) 및 'NaN' 포인트 제거
    points = np.asarray(pcd.points)
    finite_indices = np.where(np.all(np.isfinite(points), axis=1))[0]
    pcd = pcd.select_by_index(finite_indices)

    # 아웃라이어 (Outlier) 제거 (Statistical Outlier Removal)
    # print(f"  - 아웃라이어 제거 전: {len(pcd.points)} points")
    cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd = pcd.select_by_index(ind)
    # print(f"  - 아웃라이어 제거 후: {len(pcd.points)} points")

    # Z축 뒤집기 (Flip)
    pcd.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])

    return pcd


# === 5. 전체 파이프라인 실행 ===

if __name__ == "__main__":

    # --- 0. 설정 값 (사용자 환경에 맞게 수정) ---
    print("--- 0. 설정 정의 ---")

    # ### 3_8
    # # (1) 기본 입력 경로
    # RGB_IMAGE_PATH = r"data\DJI_20240424170545_0653\3_8\slice_3_8.png"
    # ORIGINAL_DEPTH_PATH = r"data\DJI_20240424170545_0653\3_8\pred_depth_raw.tif"
    # # (2) 중간/최종 출력 경로
    # # 1단계 결과물 (Sobel 엣지 맵)
    # GENERATED_EDGE_PATH = r"data\DJI_20240424170545_0653\3_8\slice_3_8_sobel_edge_map.png"
    # # 2단계 결과물 (그룹 시각화)
    # GROUP_VISUALIZATION_PATH = r"data\DJI_20240424170545_0653\3_8\slice_3_8_contour_groups.png"
    # # 3단계 결과물 (회귀된 뎁스 맵)
    # REGRESSED_DEPTH_PATH = r"data\DJI_20240424170545_0653\3_8\slice_3_8_refined.tif"

    ### 3_9
    # (1) 기본 입력 경로
    RGB_IMAGE_PATH = r"data\DJI_20240424170545_0653\3_9\slice_3_9.png"
    ORIGINAL_DEPTH_PATH = r"data\DJI_20240424170545_0653\3_9\pred_depth_raw.tif"
    # (2) 중간/최종 출력 경로
    # 1단계 결과물 (Sobel 엣지 맵)
    GENERATED_EDGE_PATH = r"data\DJI_20240424170545_0653\3_9\slice_3_9_sobel_edge_map.png"
    # 2단계 결과물 (그룹 시각화)
    GROUP_VISUALIZATION_PATH = r"data\DJI_20240424170545_0653\3_9\slice_3_9_contour_groups.png"
    # 3단계 결과물 (회귀된 뎁스 맵)
    REGRESSED_DEPTH_PATH = r"data\DJI_20240424170545_0653\3_9\slice_3_9_refined.tif"

    # ### 4_8
    # # (1) 기본 입력 경로
    # RGB_IMAGE_PATH = r"data\DJI_20240424170545_0653\4_8\slice_4_8.png"
    # ORIGINAL_DEPTH_PATH = r"data\DJI_20240424170545_0653\4_8\pred_depth_raw.tif"
    # # (2) 중간/최종 출력 경로
    # # 1단계 결과물 (Sobel 엣지 맵)
    # GENERATED_EDGE_PATH = r"data\DJI_20240424170545_0653\4_8\slice_4_8_sobel_edge_map.png"
    # # 2단계 결과물 (그룹 시각화)
    # GROUP_VISUALIZATION_PATH = r"data\DJI_20240424170545_0653\4_8\slice_4_8_contour_groups.png"
    # # 3단계 결과물 (회귀된 뎁스 맵)
    # REGRESSED_DEPTH_PATH = r"data\DJI_20240424170545_0653\4_8\slice_4_8_refined.tif"

    # ### 4_9
    # # (1) 기본 입력 경로
    # RGB_IMAGE_PATH = r"data\DJI_20240424170545_0653\4_9\slice_4_9.png"
    # ORIGINAL_DEPTH_PATH = r"data\DJI_20240424170545_0653\4_9\pred_depth_raw.tif"
    # # (2) 중간/최종 출력 경로
    # # 1단계 결과물 (Sobel 엣지 맵)
    # GENERATED_EDGE_PATH = r"data\DJI_20240424170545_0653\4_9\slice_4_9_sobel_edge_map.png"
    # # 2단계 결과물 (그룹 시각화)
    # GROUP_VISUALIZATION_PATH = r"data\DJI_20240424170545_0653\4_9\slice_4_9_contour_groups.png"
    # # 3단계 결과물 (회귀된 뎁스 맵)
    # REGRESSED_DEPTH_PATH = r"data\DJI_20240424170545_0653\4_9\slice_4_9_refined.tif"

    # (3) 튜닝 파라미터
    DEPTH_SCALE = 1.0 # 뎁스 맵의 픽셀 값이 이미 미터(m) 단위이므로 1.0
    
    # 1단계 (Sobel)
    SOBEL_KERNEL_SIZE = 3
    
    # 2단계 (Grouping)
    CONTOUR_THRESHOLD = 50      # 이진화 임계값 (0-255)
    CONTOUR_DILATION_KSIZE = (3, 3) # 엣지 영역 확장 커널 크기
    MIN_AREA = 2000             # 무시할 최소 픽셀 면적
    MIN_ASPECT_RATIO = 10.0     # (긴쪽/짧은쪽) 최소 종횡비
    
    # 3단계 (Regression)
    RANSAC_THRESHOLD = 15.0     # RANSAC 아웃라이어 임계값 (뎁스 스케일 기준, 15m)

    # --------------------------------------------------

    # --- 1. 뎁스 맵 -> 엣지 맵 생성 ---
    print(f"\n--- 1. 뎁스 맵 -> 엣지 맵 생성 (Sobel) ---")
    if not create_sobel_edge_map(ORIGINAL_DEPTH_PATH, GENERATED_EDGE_PATH, SOBEL_KERNEL_SIZE):
        print("1단계 엣지 맵 생성에 실패하여 중단합니다.")
        sys.exit()

    # --- 2. 엣지 맵 -> 그루핑 ---
    print(f"\n--- 2. 엣지 맵 -> 그루핑 (Contours) ---")
    labels_map_contours, group_count = group_and_visualize_contours(
        GENERATED_EDGE_PATH,
        output_path=GROUP_VISUALIZATION_PATH,
        min_area_threshold=MIN_AREA,
        min_aspect_ratio=MIN_ASPECT_RATIO,
        threshold=CONTOUR_THRESHOLD,
        dilation_ksize=CONTOUR_DILATION_KSIZE
    )
    if labels_map_contours is None or group_count == 0:
        print("2단계 Contour 그루핑에 실패했거나 그룹이 없어 중단합니다.")
        sys.exit()

    # --- 3. 뎁스 회귀 (RANSAC) ---
    print(f"\n--- 3. 뎁스 회귀 (RANSAC) ---")
    # [중요] regressed_depth_map은 파일로 저장됨과 동시에
    #       포인트 클라우드 생성을 위해 Numpy 배열로 반환됩니다.
    regressed_depth_map = calculate_and_replace_depths(
        ORIGINAL_DEPTH_PATH,
        labels_map_contours,
        group_count,
        output_depth_path=REGRESSED_DEPTH_PATH,
        ransac_threshold=RANSAC_THRESHOLD
    )
    if regressed_depth_map is None:
        print("3단계 뎁스 회귀에 실패하여 중단합니다.")
        sys.exit()

    # --- 4. 카메라 파라미터 준비 ---
    print(f"\n--- 4. 카메라 파라미터 준비 ---")
    try:
        temp_img = cv2.imread(ORIGINAL_DEPTH_PATH, cv2.IMREAD_ANYDEPTH)
        if temp_img is None: raise FileNotFoundError
        H, W = temp_img.shape
        CAMERA_INTRINSICS = {
            'fx': W * 1.5,  # 초점 거리 (Focal Length) x (추정치)
            'fy': H * 1.5,  # 초점 거리 (Focal Length) y (추정치)
            'cx': W / 2,    # 주점 (Principal Point) x
            'cy': H / 2     # 주점 (Principal Point) y
        }
        print(f"  - 이미지 크기 (H, W): ({H}, {W})")
        print(f"  - 카메라 파라미터 (추정): {CAMERA_INTRINSICS}")
    except Exception as e:
        print(f"오류: 카메라 파라미터 계산을 위한 원본 뎁스 맵 로드 실패 ({e})")
        sys.exit()


    # --- 5. 포인트 클라우드 생성 (원본 vs 회귀) ---
    print(f"\n--- 5. 포인트 클라우드 생성 ---")

    print(f"  PCD 1 (Original) 생성 중... (RGB + {ORIGINAL_DEPTH_PATH})")
    pcd1 = create_point_cloud_from_rgbd(
        RGB_IMAGE_PATH,
        CAMERA_INTRINSICS,
        depth_path=ORIGINAL_DEPTH_PATH, # 원본 뎁스 맵 *경로* 사용
        depth_scale=DEPTH_SCALE
    )

    print(f"  PCD 2 (Regressed) 생성 중... (RGB + {REGRESSED_DEPTH_PATH})")
    pcd2 = create_point_cloud_from_rgbd(
        RGB_IMAGE_PATH,
        CAMERA_INTRINSICS,
        depth_image=regressed_depth_map, # 3단계에서 반환된 *Numpy 배열* 사용
        depth_scale=DEPTH_SCALE
    )

    # --- 6. 3D 뷰어 실행 (동기화) ---
    print(f"\n--- 6. 3D 뷰어 실행 (원본 vs 회귀 비교) ---")
    if pcd1 and pcd2:
        print("  - 뷰어 동기화를 시작합니다. 왼쪽 창(Master)을 조작하세요.")

        vis1 = o3d.visualization.Visualizer()
        vis2 = o3d.visualization.Visualizer()

        # 화면 해상도에 맞게 창 크기(width, height)와 위치(left, top) 조절
        vis1.create_window(window_name="PCD 1 - Original (Master Control)", width=1024, height=1024, left=0, top=50)
        vis2.create_window(window_name="PCD 2 - Regressed (Follower)", width=1024, height=1024, left=1024, top=50)
        
        vis1.add_geometry(pcd1)
        vis2.add_geometry(pcd2)

        # 3.5. 렌더링 옵션을 가져와 포인트 크기를 설정합니다.
        # (원하는 크기로 1.0, 2.0, 3.0 등)
        point_size = 1.0
        vis1.get_render_option().point_size = point_size
        vis2.get_render_option().point_size = point_size

        try:
            while True:
                # 1. 왼쪽(vis1) 뷰어의 카메라 파라미터를 가져옵니다.
                param = vis1.get_view_control().convert_to_pinhole_camera_parameters()
                
                # 2. 오른쪽(vis2) 뷰어에 해당 파라미터를 그대로 적용합니다.
                vis2.get_view_control().convert_from_pinhole_camera_parameters(param)
                
                # 3. 각 뷰어를 업데이트하고 이벤트를 처리합니다.
                if not vis1.poll_events() or not vis2.poll_events():
                    break
                
                vis1.update_renderer()
                vis2.update_renderer()

        finally:
            vis1.destroy_window()
            vis2.destroy_window()
            print("  - 뷰어를 종료했습니다.")

    else:
        print("오류: 유효한 포인트 클라우드를 생성하지 못했습니다. 파일 경로와 설정을 확인하세요.")