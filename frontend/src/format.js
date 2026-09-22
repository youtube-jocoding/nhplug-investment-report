export const money = (n) =>
  n == null
    ? "미확인"
    : n === 0
      ? "0원"
      : Math.abs(n) % 10000 === 0
        ? `${(n / 10000).toLocaleString("ko-KR")}만 원`
        : `${Math.round(n).toLocaleString("ko-KR")}원`;
export const pct = (n) => `${n.toFixed(1)}%`;
export const colors = ["#147c65", "#173247", "#399d99", "#7c8f9c", "#cfd5da"];
