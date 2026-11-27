import { renderHook } from "@tests/setup/test-utils";
import { useAppPosition } from "@/lib/navigation/hooks";

let mockPathname = "/app";
let mockParams = new URLSearchParams();
const mockRouter = { push: jest.fn(), replace: jest.fn() };

jest.mock("next/navigation", () => ({
  ...jest.requireActual<typeof import("@tests/setup/mocks/nextNavigation")>(
    "@tests/setup/mocks/nextNavigation"
  ).nextNavigationMock,
  usePathname: () => mockPathname,
  useSearchParams: () => mockParams,
  useRouter: () => mockRouter,
}));

beforeEach(() => {
  mockPathname = "/app";
  mockParams = new URLSearchParams();
});

test.each(["/app/plugins", "/app/plugins/oauth/complete"])(
  "recognizes %s without highlighting New chat",
  (pathname) => {
    mockPathname = pathname;
    mockParams = new URLSearchParams("chatId=existing-chat");
    const { result } = renderHook(() => useAppPosition());
    expect(result.current.isPlugins()).toBe(true);
    expect(result.current.isNewSession()).toBe(false);
    expect(result.current.isChat()).toBe(false);
    expect(result.current.href()).toBe("/app/plugins");
  }
);

test("keeps conversation routing separate from Plugins", () => {
  mockParams = new URLSearchParams("chatId=existing-chat");
  const { result } = renderHook(() => useAppPosition());
  expect(result.current.isPlugins()).toBe(false);
  expect(result.current.chat()).toBe("existing-chat");
  expect(result.current.href()).toBe("/app?chatId=existing-chat");
});

test.each(["/app/agents", "/app/agents/create", "/app/agents/edit/42"])(
  "keeps the Agents sidebar destination selected on %s",
  (pathname) => {
    mockPathname = pathname;
    const { result } = renderHook(() => useAppPosition());
    expect(result.current.isAgents()).toBe(true);
    expect(result.current.href()).toBe("/app/agents");
  }
);

test.each(["/app/projects", "/app/projects/42/chats/project-chat"])(
  "recognizes %s as part of Projects",
  (pathname) => {
    mockPathname = pathname;
    const { result } = renderHook(() => useAppPosition());
    expect(result.current.isProjects()).toBe(true);
    expect(result.current.href()).toBe("/app/projects");
    expect(result.current.isNewSession()).toBe(false);
  }
);

test("keeps project workspace links on their existing route", () => {
  mockParams = new URLSearchParams("projectId=42");
  const { result } = renderHook(() => useAppPosition());
  expect(result.current.project()).toBe(42);
  expect(result.current.href()).toBe("/app?projectId=42");
});
