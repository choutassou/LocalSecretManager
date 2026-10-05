import { expect, test, type Page } from "@playwright/test";

const rows = (page: Page) => page.getByTestId("entry-row");
const dialog = (page: Page) => page.getByRole("dialog");

/** Remove every stored entry through the API so each test starts empty. */
test.beforeEach(async ({ page, request }) => {
  const list = await (await request.post("/api/list", { data: {} })).json();
  for (const e of list.results) await request.post("/api/delete", { data: { site: e.site, username: e.username } });
  await page.goto("/");
  await expect(page.getByText("全 0 件")).toBeVisible();
});

async function register(
  page: Page,
  e: { site: string; username?: string; keywords?: string[]; password: string },
) {
  await page.getByRole("button", { name: "新規登録" }).click();
  const d = dialog(page);
  await d.getByLabel("サイト名 / アプリ名").fill(e.site);
  if (e.username) await d.getByLabel("ユーザー名").fill(e.username);
  for (const [i, k] of (e.keywords ?? []).entries()) await d.getByPlaceholder(`キーワード${i + 1}`).fill(k);
  await d.locator(".pw-input input").fill(e.password);
  await d.getByRole("button", { name: "登録", exact: true }).click();
}

test.describe("一覧・登録", () => {
  test("空の状態を表示する", async ({ page }) => {
    await expect(page.getByText("まだ登録がありません")).toBeVisible();
    await expect(rows(page)).toHaveCount(0);
  });

  test("登録すると一覧に出て、リロード後も残る", async ({ page }) => {
    await register(page, { site: "GitHub", username: "taro", keywords: ["git", "code"], password: "Secret#1" });
    await expect(page.getByText("登録しました")).toBeVisible();
    await expect(dialog(page)).toHaveCount(0);
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("GitHub");
    await expect(rows(page).first()).toContainText("taro");
    await expect(rows(page).first().locator(".tag")).toHaveText(["git", "code"]);
    await page.reload();
    await expect(rows(page)).toHaveCount(1);
    await expect(page.getByText("全 1 件")).toBeVisible();
  });

  test("パスワードは既定でマスクされ、目のアイコンで表示/非表示", async ({ page }) => {
    await register(page, { site: "A", password: "plain-pw-123" });
    const row = rows(page).first();
    await expect(row).not.toContainText("plain-pw-123");
    await row.getByRole("button", { name: "表示" }).click();
    await expect(row).toContainText("plain-pw-123");
    await row.getByRole("button", { name: "隠す" }).click();
    await expect(row).not.toContainText("plain-pw-123");
  });

  test("パスワードとユーザー名をクリップボードにコピーできる", async ({ page }) => {
    await register(page, { site: "A", username: "bob", password: "copy-me-1" });
    await rows(page).first().getByRole("button", { name: "パスワードをコピー" }).click();
    await expect(page.getByText("パスワードをコピーしました")).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("copy-me-1");
    await rows(page).first().getByRole("button", { name: "ユーザー名をコピー" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("bob");
  });

  test("サイト名もパスワードも必須", async ({ page }) => {
    await page.getByRole("button", { name: "新規登録" }).click();
    await dialog(page).getByRole("button", { name: "登録", exact: true }).click();
    await expect(dialog(page)).toBeVisible(); // blocked by native validation
    await dialog(page).getByLabel("サイト名 / アプリ名").fill("only-site");
    await dialog(page).getByRole("button", { name: "登録", exact: true }).click();
    await expect(dialog(page)).toBeVisible();
    await expect(rows(page)).toHaveCount(0);
  });

  test("空白だけのサイト名はサーバーのエラーを表示する", async ({ page }) => {
    await register(page, { site: "   ", password: "x" });
    await expect(dialog(page).getByRole("alert")).toContainText("site/app name is required");
  });

  test("ユーザー名は空でもよい (APIキー)", async ({ page }) => {
    await register(page, { site: "OpenAI API", password: "sk-xxxx" });
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("—");
  });

  test("キーワードは3個まで・空欄は無視", async ({ page }) => {
    await register(page, { site: "K", keywords: ["a", "", "c"], password: "p" });
    await expect(rows(page).first().locator(".tag")).toHaveText(["a", "c"]);
    await expect(dialog(page).getByPlaceholder("キーワード4")).toHaveCount(0);
  });

  test("Escape と × とキャンセルでダイアログが閉じる", async ({ page }) => {
    for (const close of [
      () => page.keyboard.press("Escape"),
      () => dialog(page).getByRole("button", { name: "閉じる", exact: true }).click(),
      () => dialog(page).getByRole("button", { name: "キャンセル" }).click(),
    ]) {
      await page.getByRole("button", { name: "新規登録" }).click();
      await expect(dialog(page)).toBeVisible();
      await close();
      await expect(dialog(page)).toHaveCount(0);
    }
    await expect(rows(page)).toHaveCount(0);
  });

  test("日本語や記号を含む値も保存できる", async ({ page }) => {
    await register(page, { site: "日本のサイト <b>&", username: "太郎", keywords: ["検索"], password: "パス\"'<>🔑" });
    const row = rows(page).first();
    await expect(row).toContainText("日本のサイト <b>&");
    await row.getByRole("button", { name: "表示" }).click();
    await expect(row).toContainText("パス\"'<>🔑");
  });
});

test.describe("主キー = サイト名 + ユーザー名", () => {
  test("同じサイトでもユーザー名が違えば別レコード (空ユーザー名も別)", async ({ page }) => {
    await register(page, { site: "msn.co.jp", username: "user01", password: "pw-a" });
    await register(page, { site: "msn.co.jp", password: "pw-b" });
    await expect(rows(page)).toHaveCount(2);
    await expect(page.getByText("全 2 件")).toBeVisible();
  });

  test("同じ組み合わせの新規登録は上書きせずエラー", async ({ page }) => {
    await register(page, { site: "dup", username: "u", password: "first" });
    await register(page, { site: "dup", username: "u", password: "second" });
    await expect(dialog(page).getByRole("alert")).toContainText("既に登録");
    await dialog(page).getByRole("button", { name: "キャンセル" }).click();
    await rows(page).first().getByRole("button", { name: "表示" }).click();
    await expect(rows(page).first()).toContainText("first");
    await expect(rows(page)).toHaveCount(1);
  });

  test("空ユーザー名の重複もエラー", async ({ page }) => {
    await register(page, { site: "dup", password: "first" });
    await register(page, { site: "dup", password: "second" });
    await expect(dialog(page).getByRole("alert")).toContainText("既に登録");
  });

  test("編集でユーザー名を変えると行が移動する (古い行は残らない)", async ({ page }) => {
    await register(page, { site: "s", username: "old", password: "p" });
    await rows(page).first().getByRole("button", { name: "編集" }).click();
    await dialog(page).getByLabel("ユーザー名").fill("new");
    await dialog(page).getByRole("button", { name: "更新" }).click();
    await expect(page.getByText("更新しました")).toBeVisible();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("new");
    await expect(rows(page).first()).not.toContainText("old");
  });

  test("編集でユーザー名を空にでき、別レコードと衝突するならエラー", async ({ page }) => {
    await register(page, { site: "s", username: "u", password: "p1" });
    await register(page, { site: "s", password: "p2" });
    await rows(page).filter({ hasText: "u" }).first().getByRole("button", { name: "編集" }).click();
    await dialog(page).getByLabel("ユーザー名").fill("");
    await dialog(page).getByRole("button", { name: "更新" }).click();
    await expect(dialog(page).getByRole("alert")).toContainText("既に登録");
    await expect(rows(page)).toHaveCount(2);
  });

  test("削除は選んだ行だけを消す", async ({ page }) => {
    await register(page, { site: "msn.co.jp", username: "user01", password: "a" });
    await register(page, { site: "msn.co.jp", password: "b" });
    await rows(page).filter({ hasText: "user01" }).getByRole("button", { name: "削除" }).click();
    await page.getByRole("button", { name: "削除する" }).click();
    await expect(page.getByText("削除しました")).toBeVisible();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).not.toContainText("user01");
    await page.reload();
    await expect(rows(page)).toHaveCount(1);
  });
});

test.describe("編集・削除", () => {
  test("編集でパスワードとキーワードを更新できる", async ({ page }) => {
    await register(page, { site: "s", keywords: ["x"], password: "old" });
    await rows(page).first().getByRole("button", { name: "編集" }).click();
    await expect(dialog(page).getByLabel("サイト名 / アプリ名")).toHaveValue("s");
    await expect(dialog(page).getByPlaceholder("キーワード1")).toHaveValue("x");
    await expect(dialog(page).locator(".pw-input input")).toHaveValue("old");
    await dialog(page).getByPlaceholder("キーワード2").fill("y");
    await dialog(page).locator(".pw-input input").fill("new-pw");
    await dialog(page).getByRole("button", { name: "更新" }).click();
    const row = rows(page).first();
    await row.getByRole("button", { name: "表示" }).click();
    await expect(row).toContainText("new-pw");
    await expect(row.locator(".tag")).toHaveText(["x", "y"]);
    await expect(rows(page)).toHaveCount(1);
  });

  test("サイト名の変更は名前変更として扱われる", async ({ page }) => {
    await register(page, { site: "before", password: "p" });
    await rows(page).first().getByRole("button", { name: "編集" }).click();
    await dialog(page).getByLabel("サイト名 / アプリ名").fill("after");
    await dialog(page).getByRole("button", { name: "更新" }).click();
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("after");
  });

  test("削除の確認でキャンセルすると残る", async ({ page }) => {
    await register(page, { site: "keep", password: "p" });
    await rows(page).first().getByRole("button", { name: "削除" }).click();
    await expect(page.getByText("取り消せません")).toBeVisible();
    await page.getByRole("button", { name: "キャンセル" }).click();
    await expect(rows(page)).toHaveCount(1);
  });

  test("削除確認にユーザー名が表示される", async ({ page }) => {
    await register(page, { site: "s", username: "who", password: "p" });
    await rows(page).first().getByRole("button", { name: "削除" }).click();
    await expect(page.getByRole("alertdialog")).toContainText("(who)");
  });
});

test.describe("一覧の絞り込み", () => {
  test.beforeEach(async ({ page }) => {
    await register(page, { site: "GitHub", username: "taro", keywords: ["code"], password: "p" });
    await register(page, { site: "AWS", keywords: ["cloud"], password: "p" });
    await register(page, { site: "Gmail", username: "hanako", password: "p" });
    await expect(rows(page)).toHaveCount(3);
  });

  test("サイト名・ユーザー名・キーワードで絞り込み (大文字小文字無視)", async ({ page }) => {
    const box = page.getByLabel("絞り込み");
    await box.fill("github");
    await expect(rows(page)).toHaveCount(1);
    await box.fill("HANAKO");
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("Gmail");
    await box.fill("cloud");
    await expect(rows(page).first()).toContainText("AWS");
    await expect(page.getByText("1 件に絞り込み中")).toBeVisible();
    await box.fill("zzz");
    await expect(page.getByText("条件に一致するパスワードはありません")).toBeVisible();
    await box.fill("");
    await expect(rows(page)).toHaveCount(3);
  });

  test("サイト名順に並ぶ", async ({ page }) => {
    await expect(rows(page).locator("strong")).toHaveText(["AWS", "GitHub", "Gmail"]);
  });
});

test.describe("高度検索", () => {
  test.beforeEach(async ({ page }) => {
    await register(page, { site: "GitHub", username: "me", keywords: ["git", "code"], password: "pw-gh" });
    await register(page, { site: "GitHub", password: "pw-gh2" });
    await register(page, { site: "AWS", keywords: ["cloud"], password: "pw-aws" });
    await page.getByRole("tab", { name: "高度検索" }).click();
  });

  const cond = (page: Page, k: string) => page.locator(".cond").filter({ hasText: k }).locator("input");
  const run = async (page: Page, conds: Record<string, string>, expr: string) => {
    for (const k of ["A", "B", "C", "D", "E"]) await cond(page, k).fill(conds[k] ?? "");
    await page.getByLabel("論理式", { exact: false }).fill(expr);
    await page.getByRole("button", { name: "検索", exact: true }).click();
  };

  test("A〜Eの5条件入力欄がある", async ({ page }) => {
    await expect(page.locator(".cond")).toHaveCount(5);
  });

  test("A||B", async ({ page }) => {
    await run(page, { A: "git", B: "cloud" }, "A||B");
    await expect(page.getByText("検索結果")).toBeVisible();
    await expect(rows(page)).toHaveCount(3);
  });

  test("A&&B は該当なし", async ({ page }) => {
    await run(page, { A: "git", B: "cloud" }, "A&&B");
    await expect(page.getByText("該当するパスワードはありません")).toBeVisible();
  });

  test("A&&(B||C) と ! が使える", async ({ page }) => {
    await run(page, { A: "hub", B: "code", C: "zzz" }, "A&&(B||C)");
    await expect(rows(page)).toHaveCount(1);
    await run(page, { A: "hub", B: "code" }, "A&&!B");
    await expect(rows(page)).toHaveCount(1);
    await expect(rows(page).first()).toContainText("—");
  });

  test("結果のパスワードを表示・コピーできる", async ({ page }) => {
    await run(page, { A: "aws" }, "A");
    const row = rows(page).first();
    await row.getByRole("button", { name: "表示" }).click();
    await expect(row).toContainText("pw-aws");
    await row.getByRole("button", { name: "パスワードをコピー" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("pw-aws");
  });

  test("不正な論理式はエラー表示", async ({ page }) => {
    await run(page, { A: "git" }, "A &&");
    await expect(page.getByRole("alert")).toBeVisible();
    await run(page, { A: "git" }, "A & B");
    await expect(page.getByRole("alert")).toBeVisible();
    await run(page, { A: "git" }, "A||F");
    await expect(page.getByRole("alert")).toBeVisible();
  });

  test("空の条件を参照するとエラー", async ({ page }) => {
    await run(page, { A: "git" }, "A||B");
    await expect(page.getByRole("alert")).toContainText("condition B is empty");
  });

  test("エラー後に正しい式で再検索するとエラーが消える", async ({ page }) => {
    await run(page, { A: "git" }, "A &&");
    await expect(page.getByRole("alert")).toBeVisible();
    await run(page, { A: "git" }, "A");
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(rows(page)).toHaveCount(2);
  });

  test("検索結果から削除すると結果と一覧の両方から消える", async ({ page }) => {
    await run(page, { A: "aws" }, "A");
    await rows(page).first().getByRole("button", { name: "削除" }).click();
    await page.getByRole("button", { name: "削除する" }).click();
    await expect(rows(page)).toHaveCount(0);
    await page.getByRole("tab", { name: "一覧" }).click();
    await expect(rows(page)).toHaveCount(2);
  });

  test("検索結果から編集して保存すると結果が消えて古い表示が残らない", async ({ page }) => {
    await run(page, { A: "aws" }, "A");
    await rows(page).first().getByRole("button", { name: "編集" }).click();
    await dialog(page).locator(".pw-input input").fill("changed");
    await dialog(page).getByRole("button", { name: "更新" }).click();
    await expect(page.getByText("検索結果")).toHaveCount(0);
  });

  test("Enterキーで検索できる", async ({ page }) => {
    await cond(page, "A").fill("aws");
    await page.getByLabel("論理式").fill("A");
    await page.getByLabel("論理式").press("Enter");
    await expect(rows(page)).toHaveCount(1);
  });
});

test.describe("パスワード生成", () => {
  test("生成タブ: 既定は8〜64、生成・コピーできる", async ({ page }) => {
    await page.getByRole("tab", { name: "生成" }).click();
    await expect(page.getByLabel("最小長")).toHaveValue("8");
    await expect(page.getByLabel("最大長")).toHaveValue("64");
    for (const n of ["大文字", "小文字", "記号"]) await expect(page.getByLabel(n)).toBeChecked();
    await page.getByRole("button", { name: "生成", exact: true }).click();
    const out = page.locator(".gen-out code");
    await expect(out).not.toContainText("クリックすると");
    const pw = (await out.textContent()) ?? "";
    expect(pw.length).toBeGreaterThanOrEqual(8);
    expect(pw.length).toBeLessThanOrEqual(64);
    await page.getByRole("button", { name: "コピー" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(pw);
  });

  test("文字種と長さの指定が反映される", async ({ page }) => {
    await page.getByRole("tab", { name: "生成" }).click();
    await page.getByLabel("小文字").uncheck();
    await page.getByLabel("記号").uncheck();
    await page.getByLabel("最小長").fill("30");
    await page.getByLabel("最大長").fill("30");
    for (let i = 0; i < 5; i++) {
      await page.getByRole("button", { name: "生成", exact: true }).click();
      await expect(page.locator(".gen-out code")).toHaveText(/^[A-Z0-9]{30}$/);
    }
  });

  test("数字のみ (全部オフ)", async ({ page }) => {
    await page.getByRole("tab", { name: "生成" }).click();
    for (const n of ["大文字", "小文字", "記号"]) await page.getByLabel(n).uncheck();
    await page.getByLabel("最小長").fill("12");
    await page.getByLabel("最大長").fill("12");
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await expect(page.locator(".gen-out code")).toHaveText(/^\d{12}$/);
  });

  test("不正な長さはエラー通知", async ({ page }) => {
    await page.getByRole("tab", { name: "生成" }).click();
    await page.getByLabel("最小長").fill("20");
    await page.getByLabel("最大長").fill("10");
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await expect(page.locator(".toast.error")).toContainText("invalid length range");
  });

  test("登録ダイアログ内で生成して使う → 保存される", async ({ page }) => {
    await page.getByRole("button", { name: "新規登録" }).click();
    const d = dialog(page);
    await d.getByLabel("サイト名 / アプリ名").fill("gen-site");
    await d.getByLabel("最小長").fill("20");
    await d.getByLabel("最大長").fill("20");
    await d.getByRole("button", { name: "生成", exact: true }).click();
    const generated = (await d.locator(".gen-out code").textContent()) ?? "";
    expect(generated).toHaveLength(20);
    await d.getByRole("button", { name: "このパスワードを使う" }).click();
    await expect(d.locator(".pw-input input")).toHaveValue(generated);
    await d.getByRole("button", { name: "登録", exact: true }).click();
    const row = rows(page).first();
    await row.getByRole("button", { name: "表示" }).click();
    await expect(row).toContainText(generated);
  });

  test("ダイアログのパスワード欄: 表示/隠す切替", async ({ page }) => {
    await page.getByRole("button", { name: "新規登録" }).click();
    const input = dialog(page).locator(".pw-input input");
    await expect(input).toHaveAttribute("type", "password");
    await dialog(page).getByRole("button", { name: "表示", exact: true }).click();
    await expect(input).toHaveAttribute("type", "text");
  });
});

test.describe("ナビゲーションと表示", () => {
  test("タブ切替で内容が変わる", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "登録済みパスワード" })).toBeVisible();
    await page.getByRole("tab", { name: "高度検索" }).click();
    await expect(page.getByRole("heading", { name: "高度検索" })).toBeVisible();
    await page.getByRole("tab", { name: "生成" }).click();
    await expect(page.getByRole("heading", { name: "パスワード生成" })).toBeVisible();
  });

  test("コンソールエラーが出ない", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(e.message));
    await page.reload();
    await register(page, { site: "x", password: "p" });
    await page.getByRole("tab", { name: "高度検索" }).click();
    await page.getByRole("tab", { name: "生成" }).click();
    expect(errors).toEqual([]);
  });

  test("スマートフォン幅でも横スクロールせず操作できる", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 700 });
    await register(page, { site: "mobile-site", username: "a-rather-long-user-name@example.com", password: "p" });
    await expect(rows(page).first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await rows(page).first().getByRole("button", { name: "編集" }).click();
    await expect(dialog(page)).toBeVisible();
  });

  test("ダークモードで表示できる", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).not.toBe("rgb(244, 245, 249)");
  });
});
