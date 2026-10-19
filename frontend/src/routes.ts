// Browser routes. The code is encoded whole, so URL-like codes stay one path segment;
// the router hands it back decoded as the `:code` param.
export const codePagePath = (code: string) => `/codes/${encodeURIComponent(code)}`
