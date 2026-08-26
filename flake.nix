{
  description = "Etiquettes";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;

      pkgsFor = forAllSystems (system:
        import nixpkgs {
          inherit system;
        }
      );

      packageFor = system:
        let
          pkgs = pkgsFor.${system};

          python = pkgs.python3.withPackages (ps: [
            ps.pypdf
          ]);
        in
          pkgs.writeShellScriptBin "label-server" ''
            exec ${python}/bin/python ${./label.py}
          '';
    in
    {
      packages = forAllSystems (system: {
        default = packageFor system;
        label-server = packageFor system;
      });

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.services.label-server;
        in
        {
          options.services.label-server = {
            enable = lib.mkEnableOption "Etiquettes";

            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.system}.label-server;
              defaultText = lib.literalExpression
                "self.packages.${pkgs.system}.label-server";
              description = "Label server package to run.";
            };

            host = lib.mkOption {
              type = lib.types.str;
              default = "127.0.0.1";
              description = "Address on which the server listens.";
            };

            port = lib.mkOption {
              type = lib.types.port;
              default = 8000;
              description = "TCP port on which the server listens.";
            };

            user = lib.mkOption {
              type = lib.types.str;
              default = "label-server";
              description = "User account used to run the service.";
            };

            group = lib.mkOption {
              type = lib.types.str;
              default = "label-server";
              description = "Group used to run the service.";
            };
          };

          config = lib.mkIf cfg.enable {
            systemd.services.label-server = {
              description = "Etiquettes";
              wantedBy = [ "multi-user.target" ];
              after = [ "network.target" ];

              environment = {
                LABEL_SERVER_HOST = cfg.host;
                LABEL_SERVER_PORT = toString cfg.port;
              };

              serviceConfig = {
                ExecStart = "${cfg.package}/bin/label-server";

                User = cfg.user;
                Group = cfg.group;

                Restart = "on-failure";
                RestartSec = "2s";

                # The server only needs temporary files while invoking Typst.
                PrivateTmp = true;

                # Basic service hardening.
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = true;
                PrivateDevices = true;

                # Typst needs to be available in PATH.
                # The Python server invokes it using shutil.which().
                Environment = "PATH=${pkgs.typst}/bin";

                # Give the process a reasonable resource limit.
                LimitNOFILE = 4096;
              };

              path = [
                pkgs.typst
              ];
            };

            users.users = lib.mkIf (cfg.user == "label-server") {
              label-server = {
                isSystemUser = true;
                group = cfg.group;
              };
            };

            users.groups = lib.mkIf (cfg.group == "label-server") {
              label-server = {};
            };
          };
        };

      # Convenient development shell:
      # nix develop
      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};

          python = pkgs.python3.withPackages (ps: [
            ps.pypdf
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.typst
            ];
          };
        }
      );
    };
}
