-- RossiAPP: local DaVinci Resolve in-process bridge.
-- Start from Workspace > Scripts > Utility > YouTubeImporterBridge once per Resolve session.
-- This script supports ping, read-only timeline analysis, and import/append requests. It never
-- executes arbitrary Lua supplied by the desktop client.

local bridge_version = "0.1.7"
local state_dir = os.getenv("USERPROFILE") .. "\\.ytresolve-importer"
local request_path = state_dir .. "\\request.lua"
local pref_prefix = "Global.RossiYouTubeImporter."
local last_id = ""
local session_id = "unknown"

local function set_status(value)
    pcall(function()
        fusion:SetPrefs(pref_prefix .. "Status", tostring(value))
        fusion:SavePrefs()
    end)
end

local function resolve_version()
    local ok, value = pcall(function()
        return resolve and resolve:GetVersionString() or "unavailable"
    end)
    return ok and tostring(value) or "unavailable"
end

local function safe_string(v)
    if v == nil then return "" end
    return tostring(v):gsub("\\", "\\\\"):gsub('"', '\\"')
        :gsub("\r", "\\r"):gsub("\n", "\\n")
end

local function json_result(id, ok, message, version, project, timeline, media_name)
    return string.format(
        '{"id":"%s","ok":%s,"message":"%s","resolve_version":"%s","project":"%s","timeline":"%s","media":"%s"}',
        safe_string(id), ok and "true" or "false", safe_string(message), safe_string(version),
        safe_string(project), safe_string(timeline), safe_string(media_name)
    )
end

local function hex(s)
    return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end

local function reply(id, ok, message, version, project, timeline, media_name)
    local saved, err = pcall(function()
        local payload = id .. ":" .. hex(json_result(id, ok, message, version, project, timeline, media_name))
        fusion:SetPrefs(pref_prefix .. "Response", payload)
        fusion:SavePrefs()
    end)
    if not saved then
        set_status("response_error:" .. tostring(err))
        print("YouTube Importer bridge could not save response: " .. tostring(err))
    else
        set_status("running:" .. session_id .. ":" .. resolve_version())
    end
end

local function handle(req)
    if type(req) ~= "table" or type(req.id) ~= "string" or type(req.action) ~= "string" then
        return false, "Request is malformed"
    end
    if req.action == "ping" then
        return true, "Bridge is running", "", "", ""
    end
    if req.action == "delete_gaps" then
        local project_manager = resolve:GetProjectManager()
        local project = project_manager and project_manager:GetCurrentProject()
        if not project then return false, "No project is open", "", "", "" end
        local timeline = project:GetCurrentTimeline()
        if not timeline then return false, "No active timeline", project:GetName(), "", "" end
        local call_ok, deleted = pcall(function() return timeline:DeleteGaps() end)
        if not call_ok then
            return false, "Resolve could not close timeline gaps: " .. tostring(deleted),
                project:GetName(), timeline:GetName(), ""
        end
        if deleted == false then
            return false, "Resolve did not close the timeline gaps",
                project:GetName(), timeline:GetName(), ""
        end
        return true, "All gaps in the active timeline were closed",
            project:GetName(), timeline:GetName(), ""
    end
    if req.action == "analyze_timeline" then
        local project_manager = resolve:GetProjectManager()
        local project = project_manager and project_manager:GetCurrentProject()
        if not project then return false, "No project is open", "", "", "" end
        local timeline = project:GetCurrentTimeline()
        if not timeline then return false, "No active timeline", project:GetName(), "", "" end
        local findings = {}
        local function add(severity, category, track, detail)
            findings[#findings + 1] = string.format(
                '{"severity":"%s","category":"%s","track":"%s","detail":"%s"}',
                safe_string(severity), safe_string(category), safe_string(track), safe_string(detail))
        end
        local function scan_tracks(track_type, label)
            local count = timeline:GetTrackCount(track_type) or 0
            for track_index = 1, count do
                local track_name = label .. " " .. tostring(track_index)
                pcall(function()
                    local named = timeline:GetTrackName(track_type, track_index)
                    if named and named ~= "" then track_name = tostring(named) end
                end)
                local items = timeline:GetItemListInTrack(track_type, track_index) or {}
                if #items == 0 then
                    add("info", "Traccia vuota", track_name, "La traccia non contiene clip.")
                else
                    table.sort(items, function(a, b) return (a:GetStart() or 0) < (b:GetStart() or 0) end)
                    local previous_end = nil
                    for _, item in ipairs(items) do
                        local start_frame = tonumber(item:GetStart())
                        local end_frame = tonumber(item:GetEnd())
                        if start_frame and previous_end and start_frame > previous_end then
                            local gap = start_frame - previous_end
                            if gap > 1 then
                                add("warning", "Spazio vuoto", track_name,
                                    tostring(gap) .. " fotogrammi tra clip consecutive.")
                            end
                        end
                        if end_frame then previous_end = math.max(previous_end or end_frame, end_frame) end
                        local ok_media, media = pcall(function() return item:GetMediaPoolItem() end)
                        if ok_media and media then
                            local ok_path, file_path = pcall(function() return media:GetClipProperty("File Path") end)
                            if ok_path and type(file_path) == "string" and file_path ~= ""
                                and bmd and bmd.fileexists and not bmd.fileexists(file_path) then
                                add("error", "File mancante", track_name,
                                    tostring(item:GetName()) .. " — " .. file_path)
                            end
                        end
                    end
                end
            end
        end
        scan_tracks("video", "Video")
        scan_tracks("audio", "Audio")
        scan_tracks("subtitle", "Sottotitoli")
        return true, '{"findings":[' .. table.concat(findings, ",") .. ']}', project:GetName(), timeline:GetName(), ""
    end
    if req.action ~= "import_append" and req.action ~= "import_pool" then
        return false, "Unsupported action"
    end
    if type(req.path) ~= "string" or req.path == "" then
        return false, "File path is missing"
    end

    local project_manager = resolve:GetProjectManager()
    local project = project_manager and project_manager:GetCurrentProject()
    if not project then return false, "No project is open" end
    local media_pool = project:GetMediaPool()
    if not media_pool then return false, "Resolve Media Pool is unavailable" end
    local function normalize(path)
        return tostring(path or ""):gsub("/", "\\"):lower()
    end
    local function find_existing(folder)
        local clips = folder:GetClipList() or {}
        for i = 1, #clips do
            local item = clips[i]
            local ok, file_path = pcall(function() return item:GetClipProperty("File Path") end)
            if ok and normalize(file_path) == normalize(req.path) then return item end
        end
        local children = folder:GetSubFolderList() or {}
        for i = 1, #children do
            local found = find_existing(children[i])
            if found then return found end
        end
        return nil
    end
    local media = find_existing(media_pool:GetRootFolder())
    if not media then
        local imported = media_pool:ImportMedia({ req.path })
        media = type(imported) == "table" and imported[1] or nil
    end
    if not media then return false, "Resolve did not import the file into the Media Pool" end

    if req.action == "import_pool" then
        return true, "Imported into the Media Pool", project:GetName(), "", media:GetName()
    end

    local timeline = project:GetCurrentTimeline()
    if not timeline then return false, "No active timeline; file is in the Media Pool only", project:GetName(), "", media:GetName() end

    project:SetCurrentTimeline(timeline)
    pcall(function() return resolve:OpenPage("edit") end)

    -- AppendToTimeline places the clip after existing timeline content, avoiding overwrite.
    local appended = media_pool:AppendToTimeline(media)
    if type(appended) ~= "table" or not appended[1] then
        return false, "Media Pool import succeeded, but timeline insertion failed",
            project:GetName(), timeline:GetName(), media:GetName()
    end
    return true, "Imported into the Media Pool and appended to the active timeline",
        project:GetName(), timeline:GetName(), media:GetName()
end

local function read_request()
    if not bmd or type(bmd.fileexists) ~= "function" or not bmd.fileexists(request_path) then return nil end
    local chunk, load_error = loadfile(request_path)
    if not chunk then return { id = "load-error", action = "invalid", error = load_error } end
    local ok, req = pcall(chunk)
    if not ok then return { id = "load-error", action = "invalid", error = req } end
    return req
end

local ok_pid, pid = pcall(function() return bmd.getpid() end)
session_id = ok_pid and tostring(pid) or tostring(os.time())
local ok_session, previous_session = pcall(function() return fusion:GetPrefs(pref_prefix .. "Session") end)
if ok_session and tostring(previous_session or "") == session_id then
    print("YouTube Importer bridge is already running in this Resolve session.")
    return
end
set_status("starting:" .. session_id .. ":" .. resolve_version())
pcall(function()
    fusion:SetPrefs(pref_prefix .. "Session", session_id)
    fusion:SavePrefs()
end)
print("YouTube Importer bridge " .. bridge_version .. " started for Resolve " .. resolve_version() .. ".")
while true do
    local loop_ok, loop_error = pcall(function()
        bmd.wait(0.15)
        local req = read_request()
        if req and type(req) == "table" and type(req.id) == "string" and req.id ~= last_id then
            last_id = req.id
            local call_ok, succeeded, message, project_name, timeline_name, media_name = pcall(handle, req)
            if not call_ok then
                reply(req.id, false, "Resolve Lua error: " .. tostring(succeeded), resolve_version(), "", "", "")
            elseif req.action == "ping" then
                reply(req.id, succeeded, message, resolve_version(), "", "", "")
            else
                reply(req.id, succeeded, message, resolve_version(), project_name, timeline_name, media_name)
            end
        end
    end)
    if not loop_ok then
        set_status("loop_error:" .. tostring(loop_error))
        print("YouTube Importer bridge loop error: " .. tostring(loop_error))
        pcall(function() bmd.wait(1) end)
    end
end
