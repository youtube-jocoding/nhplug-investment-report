import { useState, useEffect } from "react";
import { Copy, Download, ArrowUpRight } from "lucide-react";
import { api } from "./api";
import { Modal } from "./Modal";
export function Connect({ onReport, onClose }) {
  const [credentials, setCredentials] = useState({
    brand: "namuh",
    app_key: "",
    app_secret: "",
  });
  const [market, setMarket] = useState("us");
  const [saved, setSaved] = useState(false);
  const [accounts, setAccounts] = useState([]),
    [selected, setSelected] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function run(f) {
    setError("");
    setBusy(true);
    try {
      await f();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="PLUG 데이터 연결" onClose={onClose}>
      <p>
        공식 API에서 계좌 목록과 선택한 시장의 잔고를 조회합니다. 키는 서버의
        로컬 설정에서 읽고, 계좌는 마스킹해 표시합니다.
      </p>
      <button
        disabled={busy}
        onClick={() =>
          run(async () => {
            const x = await api("accounts", {});
            setAccounts(x.accounts);
            setSelected("");
          })
        }
      >
        {busy ? "조회 중…" : "연결된 계좌 목록 조회"}
      </button>
      {accounts.length > 0 && (
        <div className="account-list">
          <label>
            분석할 시장
            <select value={market} onChange={(e) => setMarket(e.target.value)}>
              <option value="us">미국주식 · 해외조회 예수금</option>
              <option value="kr">국내주식 · 원화 예수금</option>
            </select>
          </label>
          <label>
            리포트를 만들 계좌
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">계좌를 직접 선택해 주세요</option>
              {accounts.map((a) => (
                <option value={a.ref} key={a.ref}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          <button
            className="primary"
            disabled={!selected || busy}
            onClick={() =>
              run(async () => {
                const x = await api("connect", { ref: selected, market });
                onReport(x.report);
                onClose();
              })
            }
          >
            선택한 계좌로 리포트 생성
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <details className="credential-editor" open={!!error || undefined}>
        <summary>현재 키로 다시 연결</summary>
        <p className="muted">
          키는 이 컴퓨터의 로컬 서버로 전달되어 PLUG 인증에만 사용됩니다. 인증
          성공 후 현재 사용자만 읽는 파일로 저장합니다. 채팅에 붙여 넣지 마세요.
        </p>
        <form
          autoComplete="off"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const values = credentials;
              setCredentials({ ...credentials, app_key: "", app_secret: "" });
              setAccounts([]);
              setSelected("");
              setSaved(false);
              const x = await api("credentials", values);
              setAccounts(x.accounts);
              setSaved(true);
            });
          }}
        >
          <label>
            키 발급 브랜드
            <select
              value={credentials.brand}
              onChange={(e) =>
                setCredentials({ ...credentials, brand: e.target.value })
              }
            >
              <option value="namuh">나무 Namuh PLUG</option>
              <option value="n2">N2 PLUG</option>
            </select>
          </label>
          <label>
            앱키
            <input
              type="password"
              name="plug-app-key"
              autoComplete="off"
              required
              minLength={8}
              maxLength={2048}
              value={credentials.app_key}
              onChange={(e) =>
                setCredentials({ ...credentials, app_key: e.target.value })
              }
            />
          </label>
          <label>
            앱시크릿
            <input
              type="password"
              name="plug-app-secret"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={2048}
              value={credentials.app_secret}
              onChange={(e) =>
                setCredentials({ ...credentials, app_secret: e.target.value })
              }
            />
          </label>
          <button className="primary" disabled={busy} type="submit">
            {busy ? "인증 확인 중…" : "인증 확인 후 저장하고 계좌 조회"}
          </button>
        </form>
        <p className="muted">
          <a
            href={
              credentials.brand === "namuh"
                ? "https://www.nhplug.com/intro"
                : "https://www.n2plug.com/intro"
            }
            target="_blank"
            rel="noreferrer"
          >
            PLUG 공식 포털 열기 <ArrowUpRight size={14} />
          </a>
        </p>
      </details>
      {saved && (
        <p role="status">
          API 연결을 확인하고 로컬에 저장했습니다. 위 목록에서 분석할 계좌를
          선택하세요.
        </p>
      )}
      <p className="muted">
        실제 잔고는 업종 분류가 연결되지 않은 항목을 “분류 미확인”으로
        표시합니다. 국내·미국 시장을 따로 조회하며 현금을 중복 합산하지
        않습니다.
      </p>
    </Modal>
  );
}
export function Mail({ onClose }) {
  return (
    <Modal wide title="메일 미리보기" onClose={onClose}>
      <p className="muted">
        메일에는 핵심 브리핑만 담습니다. 재무표와 조건별 전망은 상세 리포트에서
        확인하세요. 미리보기 자체는 메일을 발송하지 않습니다.
      </p>
      <div className="mail-tools">
        <a className="button" href="/api/export/eml">
          <Download size={16} />
          메일 파일 저장
        </a>
        <a className="button" href="/api/export/html">
          <Download size={16} />
          HTML 저장
        </a>
      </div>
      <iframe title="투자 리포트 메일 본문" src="/api/mail-preview" />
    </Modal>
  );
}
export function Guide({ onClose }) {
  const [content, setContent] = useState(""),
    [error, setError] = useState(""),
    [copied, setCopied] = useState(false);
  useEffect(() => {
    fetch("/docs/prompts")
      .then((r) => {
        if (!r.ok) throw Error("프롬프트를 불러오지 못했습니다.");
        return r.text();
      })
      .then((text) =>
        setContent(text.match(/```text\n([\s\S]*?)```/)?.[1]?.trim() || text),
      )
      .catch((e) => setError(e.message));
  }, []);
  return (
    <Modal wide title="3분 촬영 가이드" onClose={onClose}>
      <p>
        뉴스레터 → 실제 잔고 → 기업 분석 → Codex 예약 → Gmail 수신 순서로
        보여주세요.
      </p>
      <a href="/docs/filming" target="_blank" rel="noreferrer">
        타임코드와 전체 대본 열기 <ArrowUpRight size={14} />
      </a>
      <h3>Codex에 넣을 프롬프트</h3>
      <button
        disabled={!content}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
          } catch {
            setError("아래 텍스트를 직접 복사해 주세요.");
          }
        }}
      >
        <Copy size={16} />
        {copied ? "복사 완료" : "이 프롬프트 복사"}
      </button>
      {error && <p className="error">{error}</p>}
      <pre>{content}</pre>
    </Modal>
  );
}
