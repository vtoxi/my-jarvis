-- JARVIS Hammerspoon HTTP bridge (Phase 3)
-- Copy into ~/.hammerspoon/ or require() from init.lua. Set JARVIS_HS_TOKEN in environment or edit TOKEN below.
-- See docs/phase-3.md

local json = hs.json
local logger = hs.logger.new("jarvis", "info")

local PORT = 17339
local TOKEN = os.getenv("JARVIS_HS_TOKEN") or "change-me-in-production"

local function jsonResponse(obj, code)
  return json.encode(obj), code or 200, { ["Content-Type"] = "application/json; charset=utf-8" }
end

local function authorized(headers)
  if not headers then return false end
  local auth = headers["Authorization"] or headers["authorization"]
  return auth == ("Bearer " .. TOKEN)
end

local function handleJarvis(body)
  local req = json.decode(body)
  if not req or not req.action then
    return jsonResponse({ ok = false, error = "missing_action" }, 400)
  end
  local action = req.action
  if action == "open_app" then
    local bid = req.bundleId
    if not bid then return jsonResponse({ ok = false, error = "missing_bundleId" }, 400) end
    hs.application.launchOrFocusByBundleID(bid)
    return jsonResponse({ ok = true, action = action, bundleId = bid })
  elseif action == "focus" then
    local bid = req.bundleId
    if not bid then return jsonResponse({ ok = false, error = "missing_bundleId" }, 400) end
    local app = hs.application.applicationForBundleID(bid)
    if app then app:activate(true) end
    return jsonResponse({ ok = true, action = action, bundleId = bid })
  elseif action == "open_url" then
    local url = req.url
    if not url then return jsonResponse({ ok = false, error = "missing_url" }, 400) end
    hs.urlevent.openURL(url)
    return jsonResponse({ ok = true, action = action, url = url })
  elseif action == "delay" then
    local ms = tonumber(req.ms) or 0
    ms = math.min(ms, 5000)
    hs.timer.usleep(ms * 1000)
    return jsonResponse({ ok = true, action = action, ms = ms })
  elseif action == "tile_preset" then
    return jsonResponse({ ok = true, action = action, note = "extend tiling in your init.lua" })
  elseif action == "noop" then
    return jsonResponse({ ok = true, action = "noop" })
  end
  return jsonResponse({ ok = false, error = "unknown_action" }, 400)
end

local server = hs.httpserver.new(false, "JarvisBridge")
server:setPort(PORT)
server:setCallback(function(method, path, headers, body)
  if not authorized(headers) then
    return json.encode({ ok = false, error = "unauthorized" }), 401, { ["Content-Type"] = "application/json" }
  end
  if method == "GET" and path == "/health" then
    return "ok", 200, { ["Content-Type"] = "text/plain; charset=utf-8" }
  end
  if method == "POST" and path == "/jarvis" then
    local ok, a, b, c = pcall(handleJarvis, body or "")
    if not ok then
      logger.e("jarvis handler error: " .. tostring(a))
      return json.encode({ ok = false, error = tostring(a) }), 500, { ["Content-Type"] = "application/json" }
    end
    return a, b, c
  end
  return "not found", 404, { ["Content-Type"] = "text/plain" }
end)
server:start()
logger.i("JARVIS Hammerspoon bridge at http://127.0.0.1:" .. tostring(PORT))
