# GCD 함수 구현 (유클리드 호제법)
def gcd_recursive(a, b):
    while b != 0:
        a, b = b, a % b
    return abs(a)  # 절대값 반환으로 음수 처리


def gcd_iterative(a, b):
    while b != 0:
        a, b = b, a % b
    return abs(a)


# 시간 복잡도 비교
#
# 유클리드 호제법 (재귀 & 반복문)의 경우,
# 최악 케이스에서 O(log(min(a,b))) 의 시간 복잡성을 가집니다.
