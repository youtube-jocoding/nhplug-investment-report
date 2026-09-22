let token = "";
export async function api(path, data) {
  const response = await fetch(
    `/api/${path}`,
    data
      ? {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Report-Token": token,
          },
          body: JSON.stringify(data),
        }
      : {},
  );
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "요청에 실패했습니다.");
  if (body.token) token = body.token;
  return body;
}
