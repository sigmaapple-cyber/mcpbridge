-- Roblox Studio bridge for MCP server.
-- Place this Script in ServerScriptService and enable HttpService.

local HttpService = game:GetService("HttpService")

local function splitPath(path)
    local parts = {}
    for part in string.gmatch(path, "[^%.]+") do
        table.insert(parts, part)
    end
    return parts
end

local function resolvePath(path)
    if path == "game" then
        return game
    end

    local parts = splitPath(path)
    local current = game
    for i, part in ipairs(parts) do
        if i == 1 and part == "game" then
            -- skip root
        else
            current = current:FindFirstChild(part)
            if current == nil then
                return nil
            end
        end
    end
    return current
end

local function ensureParentAndName(fullPath)
    local parts = splitPath(fullPath)
    local name = table.remove(parts)
    local parentPath = table.concat(parts, ".")
    local parent = resolvePath(parentPath)
    return parent, name
end

local function collectInstances(root, className, nameContains, maxResults)
    local results = {}
    for _, inst in ipairs(root:GetDescendants()) do
        if #results >= maxResults then
            break
        end

        local classOk = (className == nil) or (inst.ClassName == className)
        local nameOk = (nameContains == nil) or string.find(string.lower(inst.Name), string.lower(nameContains), 1, true) ~= nil
        if classOk and nameOk then
            table.insert(results, {
                name = inst.Name,
                className = inst.ClassName,
                path = inst:GetFullName(),
            })
        end
    end
    return results
end

local function handle(action, payload)
    if action == "writescript" then
        local target = resolvePath(payload.path)
        if target == nil and payload.createIfMissing then
            local parent, name = ensureParentAndName(payload.path)
            if parent == nil then
                return { ok = false, error = "Parent path not found" }
            end
            target = Instance.new(payload.className or "Script")
            target.Name = name
            target.Parent = parent
        end

        if target == nil then
            return { ok = false, error = "Script path not found" }
        end
        if not target:IsA("LuaSourceContainer") then
            return { ok = false, error = "Target is not a script-like instance" }
        end

        target.Source = payload.source
        return { ok = true, path = target:GetFullName() }
    end

    if action == "getinstances" then
        local root = resolvePath(payload.rootPath or "game")
        if root == nil then
            return { ok = false, error = "Root path not found" }
        end

        local instances = collectInstances(root, payload.className, payload.nameContains, payload.maxResults or 100)
        return { ok = true, count = #instances, instances = instances }
    end

    if action == "change" then
        local target = resolvePath(payload.path)
        if target == nil then
            return { ok = false, error = "Path not found" }
        end

        local success, err = pcall(function()
            target[payload.property] = payload.value
        end)
        if not success then
            return { ok = false, error = err }
        end
        return { ok = true, path = target:GetFullName(), property = payload.property }
    end

    if action == "create_instance" then
        local parent = resolvePath(payload.parentPath)
        if parent == nil then
            return { ok = false, error = "Parent path not found" }
        end

        local inst = Instance.new(payload.className)
        inst.Name = payload.name or payload.className
        inst.Parent = parent
        return { ok = true, path = inst:GetFullName(), className = inst.ClassName }
    end

    if action == "delete_instance" then
        local target = resolvePath(payload.path)
        if target == nil then
            return { ok = false, error = "Path not found" }
        end

        local fullName = target:GetFullName()
        target:Destroy()
        return { ok = true, deleted = fullName }
    end

    if action == "run_command" then
        return { ok = false, error = "Custom commands must be implemented in MCPBridge.server.lua" }
    end

    return { ok = false, error = "Unknown action: " .. tostring(action) }
end

-- Minimal mock HTTP loop: replace with your preferred Studio HTTP listener plugin.
-- This script intentionally focuses on command handlers because Studio does not
-- provide a built-in raw HTTP server API.
print("MCPBridge handlers loaded. Use a Studio plugin to route HTTP POST /mcp payloads to handle(action,payload).")

_G.MCPBridgeHandle = handle
